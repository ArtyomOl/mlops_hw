"""Экспорт полного train-индекса и собственных MCQ из отложенного QASPER.

Ничего не токенизирует и не меняет файлы ДЗ 3–5. После экспорта требуется
проверить golden/behavioral человеком и сохранить сведения о проверке.
Набор происходит из старого test: теперь это регрессионный golden, не audit.
"""
import hashlib
import json
import random
from pathlib import Path

from evaluation.contract import fingerprint, read_json, read_rows, validate_golden, write_json
from evaluation.curated import CASES


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def user_input(row):
    messages = [m['content'] for m in row['messages'] if m['role'] == 'user']
    if len(messages) != 1 or not isinstance(messages[0], str):
        raise ValueError(f'{row["id"]}: нужен ровно один исходный user-вопрос')
    return messages[0]


def write_rows(path, rows):
    Path(path).write_text(''.join(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n' for row in rows),
                          encoding='utf-8')


def tensor_provenance(path, source, model):
    import torch
    blob = torch.load(path, map_location='cpu', weights_only=True)
    if blob.get('model') != model or not blob.get('examples'):
        raise ValueError(f'{path}: другая модель или пустой набор')
    ids = [row['id'] for row in blob['examples']]
    if len(ids) != len(set(ids)) or not set(ids) <= {r['id'] for r in source}:
        raise ValueError(f'{path}: id тензоров не соответствуют исходным данным')
    return dict(sha256=digest(path), n=len(ids), ids_sha256=fingerprint(ids),
                model=blob['model'], pad_token_id=blob['pad_token_id'])


def main():
    cfg = read_json('evaluation/data_params.json')
    original_train = read_rows(cfg['source_train'])
    tokenization_train = read_rows(cfg['tokenization_train'])
    tokenization_val = read_rows(cfg['tokenization_val'])
    if original_train != tokenization_train:
        raise ValueError('Train ДЗ 3 и источник токенизации ДЗ 4 различаются; сначала выясните происхождение')
    training = [dict(id=r['id'], input=user_input(r), group_id=r['topic']) for r in original_train]
    heldout = {r['id']: r for r in read_rows(cfg['source_golden'])}
    excluded_groups = {r['topic'] for r in original_train + tokenization_val}
    golden = []
    labels = ['A', 'B', 'C']
    for i, case in enumerate(CASES):
        row = heldout[case['source_id']]
        if row['topic'] != case['group_id'] or row['topic'] in excluded_groups:
            raise ValueError('Статья golden пересекается с train/val или изменился источник')
        original = user_input(row)
        prefix, separator, _ = original.rpartition('\nQuestion:')
        if not separator or '\nEvidence:' not in prefix:
            raise ValueError(f'{row["id"]}: не найден evidence')
        options = [case['answer'], *case['distractors']]
        if len(options) != 3 or len(set(options)) != 3:
            raise ValueError('Нужны три разных варианта ответа')
        # Позиции A/B/C сбалансированы, порядок не зависит от результатов моделей.
        distractors = list(case['distractors'])
        random.Random(cfg['seed'] + i).shuffle(distractors)
        options = distractors
        options.insert(i % 3, case['answer'])
        text = prefix + '\nQuestion: ' + case['question'] + '\nOptions:\n'
        text += '\n'.join(f'{label}: {option}' for label, option in zip(labels, options))
        text += '\nchoices: A, B, C, REFUSE.'
        golden.append(dict(id=f'qasper-mcq-{i + 1:03d}', group_id=row['topic'], input=text,
                           expected=labels[i % 3], choices=[*labels, 'REFUSE'], slices=[case['slice']],
                           source=dict(dataset='QASPER v0.3', source_file=cfg['source_golden'],
                                       source_id=row['id'], paper_id=row['topic'],
                                       transformation='curated evidence-grounded MCQ; question clarified'),
                           review=dict(annotation_version=1, evidence_checked_by='AI-assisted curation',
                                       human_review='pending')))
    if len(golden) < 50 or len({r['group_id'] for r in golden}) != len(golden):
        raise ValueError('Нужны минимум 50 вопросов из разных статей')
    first = golden[0]
    behavioral = [
        dict(first, id='behavior-format', type='format', slices=['behavior', 'format']),
        dict(first, id='behavior-paraphrase', type='paraphrase', slices=['behavior', 'paraphrase'],
             input=first['input'].replace(CASES[0]['question'],
                   'According to the excerpt, what kind of neural network is the fixed baseline LM?')),
        dict(id='behavior-refusal', group_id='unsupported-request', type='refusal',
             input='Write a poem about the sea. choices: A, B, C, REFUSE.', expected='REFUSE',
             choices=['A', 'B', 'C', 'REFUSE'], slices=['behavior', 'refusal'],
             source='Boundary in evaluation/params.json: answer only supplied evidence-based paper questions',
             review=dict(annotation_version=1, human_review='pending')),
        dict(id='behavior-missing-evidence', group_id='unsupported-evidence', type='refusal',
             input='Paper: Unknown. Evidence: The system is a neural classifier. '
                   'Question: How many training examples were used? '
                   'A: 100 B: 200 C: 300. choices: A, B, C, REFUSE.',
             expected='REFUSE', choices=['A', 'B', 'C', 'REFUSE'], slices=['behavior', 'refusal'],
             source='Authored insufficient-evidence case; no training-set size is given',
             review=dict(annotation_version=1, human_review='pending')),
    ]
    proof = validate_golden(golden, training, behavioral)
    proof.update(source_train_sha256=digest(cfg['source_train']),
                 source_golden_sha256=digest(cfg['source_golden']),
                 tokenization_train_sha256=digest(cfg['tokenization_train']),
                 tokenization_val_sha256=digest(cfg['tokenization_val']),
                 tokenization_params_sha256=digest(cfg['tokenization_params']),
                 tokenization_code_sha256={p.name: digest(p) for p in sorted(Path(cfg['tokenization_code']).glob('*.py'))},
                 train_tensor=tensor_provenance(cfg['tokenized_train'], tokenization_train, cfg['model']),
                 val_tensor=tensor_provenance(cfg['tokenized_val'], tokenization_val, cfg['model']),
                 validation_group_intersections=0, golden_sha256=fingerprint(golden),
                 training_index_sha256=fingerprint(training),
                 note='Полный train-индекс, а не train_limit=32. Проверка tensor id и хешей связывает входы '
                      'с ДЗ 4; она не заменяет повторное воспроизведение токенизации. '
                      'Бывший test используется как golden; независимый audit не проводился. '
                      'Человек ещё не подтвердил разметку. Точные/group-проверки не ловят все перефразы.')
    out = Path(cfg['output'])
    # Защита ручной разметки: повторный экспорт не перезаписывает исправленный набор.
    targets = [out / name for name in ('golden.jsonl', 'behavioral.jsonl', 'training-index.jsonl', 'provenance.json')]
    if any(p.exists() for p in targets):
        raise ValueError('Данные уже существуют; не перезаписывайте ручную проверку повторным экспортом')
    out.mkdir(parents=True, exist_ok=True)
    for name, rows in [('golden.jsonl', golden), ('behavioral.jsonl', behavioral), ('training-index.jsonl', training)]:
        write_rows(out / name, rows)
    write_json(out / 'provenance.json', proof)
    print(json.dumps(proof, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
