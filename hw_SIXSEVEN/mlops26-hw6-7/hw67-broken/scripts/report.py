"""Единый отчёт A+B: постобработка сохранённых результатов вне кода измерения.

Генератор не создаёт фиктивные loss, runs, проверки хранения или решение о
champion. Пары ответов подбираются для последующего ручного разбора.
"""
import csv
import json
from pathlib import Path

from evaluation.cli import current_reports
from evaluation.contract import fingerprint, read_json, read_rows
from evaluation.solution import quality_gate
from src.common import connect, load_params


def describe(metrics):
    return (f"n={metrics['n']}, correct={metrics['correct']}, valid={metrics['valid']}, "
            f"errors={metrics['errors']}; accuracy={metrics['accuracy']:.6f}, "
            f"format_rate={metrics['format_rate']:.6f}")


def literal(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def main():
    from mlflow import MlflowClient
    from src.promote import select
    from src.report import main as comparison_report
    params = load_params()
    connect(params)
    client = MlflowClient()
    sweep = read_json('metrics/sweep.json')
    best = select(client, params, sweep)
    baseline, candidate = current_reports()
    config = read_json('evaluation/params.json')
    protocol = read_json('docs/protocol.json')
    if (protocol['protocol_sha256'] != candidate['protocol_sha256']
            or protocol['candidate'] != candidate['model'] or protocol['baseline'] != baseline['model']):
        raise ValueError('Результаты не соответствуют протоколу, закреплённому до оценки')
    verdict = read_json('metrics/quality-gate.json')
    try:
        quality_gate(baseline, candidate, config['critical_slices'])
        passed, reason = True, 'Все проверки качества пройдены'
    except ValueError as exc:
        passed, reason = False, str(exc)
    if verdict.get('passed') is not passed:
        raise ValueError('Сохранённое решение устарело; повторите make eval')
    negative = read_json('metrics/negative-gate.json')
    if negative.get('rejected') is not True:
        raise ValueError('Нет подтверждённого отказа на испорченной копии')
    storage = read_json('metrics/storage-check.json')
    comparison_report()
    comparison = list(csv.DictReader(Path('docs/comparison.csv').open(encoding='utf-8')))
    rows = {r['id']: r for r in read_rows(config['golden'])}
    a = {r['id']: r for r in baseline['per_item']}
    b = {r['id']: r for r in candidate['per_item']}
    improved = [key for key in rows if not a[key]['correct'] and b[key]['correct']]
    regressed = [key for key in rows if a[key]['correct'] and not b[key]['correct']]
    if read_json('metrics/eval-diff.json') != dict(improved=improved, regressed=regressed):
        raise ValueError('Сохранённый diff не соответствует ответам')
    champion = None
    registered = client.get_registered_model(candidate['model']['name'])
    if 'champion' in registered.aliases:
        champion = client.get_model_version_by_alias(candidate['model']['name'], 'champion')
    accepted = (champion is not None and str(champion.version) == candidate['model']['version']
                and champion.run_id == candidate['model']['run_id'])
    if accepted:
        released = read_json('metrics/released.json')
        if (not passed or released['model'] != candidate['model']
                or released['protocol_sha256'] != candidate['protocol_sha256']
                or released['evaluation_run_id'] != candidate['evaluation_run_id']):
            raise ValueError('Champion не подтверждён текущим качеством и артефактом выпуска')
    uri = params['tracking']['uri'].rstrip('/')
    eval_run = client.get_run(candidate['evaluation_run_id'])
    eval_link = f'{uri}/#/experiments/{eval_run.info.experiment_id}/runs/{eval_run.info.run_id}'
    text = [
        '# ДЗ 6+7: выбор адаптера и качество ответов', '',
        f"Сравнено {len(comparison)} отдельных законченных runs одного sweep `{sweep['parent_id']}`. "
        f"Лучший run: `{best.info.run_id}` ({best.data.tags['candidate']}). "
        f"Val loss: {best.data.metrics['base_val_loss']:.8f} → {best.data.metrics['final_val_loss']:.8f}.", '',
        f"Бюджет каждой конфигурации: {literal(params['train'])}. "
        'Фиксированы база, train/val, seed и бюджет; менялись lr, r и target_modules. '
        'Четыре шага и восемь val-примеров позволяют выбрать учебного кандидата, '
        'но не доказывают устойчивого преимущества. Ресурсы и loss всех runs — в comparison.csv.', '',
        'Время и память — короткие измерения в одном процессе. Первый запуск включает прогрев; '
        'MPS driver_allocated_memory включает кеши драйвера. Эти числа не являются независимым '
        'бенчмарком скорости или чистой памяти адаптера.', '',
        f"Baseline: `{literal(baseline['model'])}`. Candidate: `{literal(candidate['model'])}`.", '',
        f"Протокол закреплён до оценки: {protocol['created_at']}, SHA256 `{candidate['protocol_sha256']}`; "
        f"golden: `{candidate['golden_sha256']}`. "
        'Один system prompt, do_sample=False, seed и лимит генерации для обеих версий. '
        'Expected не передавался модели. Полностью оценены только база и один кандидат.', '',
        'Критические срезы закреплены до измерения в evaluation/params.json. '
        'numeric проверяет точные числа, где близкая формулировка не исправляет ошибочный результат; '
        'method проверяет выбор метода — основное содержание вопросов по NLP-статьям. '
        'dataset проверяет источники данных, metric — способы оценки.', '',
        'Baseline: ' + describe(baseline['overall']) + '.',
        'Candidate: ' + describe(candidate['overall']) + '.', '',
    ]
    for name in sorted(baseline['slices']):
        text.append(f"- {name}: baseline {describe(baseline['slices'][name])}; "
                    f"candidate {describe(candidate['slices'][name])}.")
    text.extend(['', 'Срезы могут пересекаться; общий n считается по вопросам, а не суммой срезов.', '',
                 f'Исправлены id: {literal(improved)}. Потеряны id: {literal(regressed)}.', '',
                 f'Behavioral: baseline {describe(baseline["behavioral"]["overall"])}; '
                 f'candidate {describe(candidate["behavioral"]["overall"])}.', ''])
    for item in candidate['behavioral']['per_item']:
        text.append(f"- {item['id']}: valid={item['valid']}, correct={item['correct']}; raw={literal(item['raw'])}.")
    state = ('принят, champion назначен текущей версии' if accepted else
             'качество прошло, но champion этой версии не назначен' if passed else 'не принят')
    text.extend(['', f'Решение: **{state}**. Gate: {reason}.', '',
                 f"Отрицательная проверка: отказ, причина — {negative['reason']}. "
                 'Испорчена отдельная копия raw-ответов; реальные веса и aliases не менялись.', '',
                 f"Проверка хранения: run `{storage['run_id']}`, probe SHA256 `{storage['sha256']}`. "
                 'Файл получен после force-recreate контейнера; обычного restart недостаточно.', '',
                 f'[Оценочный run MLflow]({eval_link}).', '',
                 '## Пять пар для ручного разбора', '',
                 'Ниже автоматическая подборка реальных ответов. Перед сдачей человек должен '
                 'сверить evidence, разметку и добавить собственные комментарии.', ''])
    chosen = list(dict.fromkeys(regressed[:2] + improved[:2] + list(rows)))[:5]
    reviews_path = Path('docs/pair-review.json')
    reviews = read_json(reviews_path) if reviews_path.exists() else {}
    if reviews:
        if len(reviews) != 5 or not set(reviews) <= rows.keys():
            raise ValueError('В разборе нужны пять существующих id golden')
        chosen = list(reviews)
    for key in chosen:
        text.extend([f'### {key}', '', rows[key]['input'], '',
                     f"Эталон: `{rows[key]['expected']}`. Источник: {literal(rows[key]['source'])}.", '',
                     f"Baseline raw: {literal(a[key]['raw'])}; valid={a[key]['valid']}, correct={a[key]['correct']}.", '',
                     f"Candidate raw: {literal(b[key]['raw'])}; valid={b[key]['valid']}, correct={b[key]['correct']}.", '',
                     'Неверный или невалидный ответ даёт 0. Содержательно верная фраза без строгого JSON '
                      'также даёт 0 по заранее закреплённому контракту.', ''])
        if key in reviews:
            text.extend(['Разбор с помощью AI: ' + reviews[key], ''])
    pending = sum(r.get('review', {}).get('human_review') != 'approved' for r in rows.values())
    text.extend(['## Ограничения', '',
                 f'Golden содержит собственные MCQ по 50 отдельным статьям отложенного QASPER. '
                 f'Не подтверждены человеком: {pending} из {len(rows)}. Нельзя выдавать AI-проверку за человеческую. '
                 'Индекс включает весь исходный train, а не только 32 примера обучения. '
                 'Контроль ловит точные нормализованные совпадения и пересечения статей; '
                 'он не гарантирует отсутствия всех смысловых утечек. В provenance.json сохранены '
                 'хеши исходников, тензоров и кода токенизации и проверка id. '
                 'Отложенная часть ДЗ 3 стала регрессионным golden, независимый финальный audit не выполнялся.', '',
                 'BLEU/ROUGE/BERTScore оценивают сходство текста: неверный факт может совпадать с эталоном '
                 'по большинству слов, а краткий верный ответ — получить низкое сходство. '
                 'MCQ scorer проверяет метку программно. Модель-судья полезна для полноты и обоснованности '
                 'открытых ответов, но подвержена эффекту порядка, многословия, предпочтению стиля и ошибкам. '
                 'Для judge нужны слепые A/B и B/A, фиксированная рубрика, сохранённые входы/вердикты '
                 'и сверка с человеком; платный API здесь не использовался.', '',
                 'При отказе сохраняем candidate и прежний champion. Следующий шаг — разобрать ошибки '
                 'на отдельном dev-наборе и повторить сопоставимый эксперимент, сохраняя пороги и историю baseline.', ''])
    docs = Path('docs')
    docs.mkdir(exist_ok=True)
    (docs / 'conclusion.md').write_text('\n'.join(text), encoding='utf-8')
    defects = [
        '# Четыре дефекта части A', '',
        '1. Общий all-candidates run смешивал параметры и метрики моделей; условие log_params '
        'скрывало различия. Исправление: отдельный nested run внутри цикла и безусловный log_params. '
        f'Доказательство: {len(comparison)} runs в sweep, comparison.csv и проверки 1/3 tests/check.py.', '',
        '2. Postgres переживал замену контейнера, но /mlartifacts лежал в слое контейнера. '
        'Исправление: именованный volume artifacts:/mlartifacts. '
        f"Доказательство: storage-check.json, run {storage['run_id']}, SHA256 {storage['sha256']}; проверка 8.", '',
        '3. provenance вычислял data_train_sha256/data_val_sha256, но sweep отбрасывал их. '
        'Исправление: передаём полный provenance родительскому и каждому дочернему run. '
        'Доказательство: одинаковые актуальные хеши в tags всех runs, проверки 2 и src.promote.select.', '',
        '4. promote вычислял val/base, но не вызывал gate до регистрации и смены alias. '
        'Исправление: gate(run, threshold) первым действием; отказ до любой записи в реестр. '
        'CLI src.promote создаёт только candidate; champion назначает evaluation.cli после качества. '
        'Доказательство: проверка 6 задаёт нулевой loss-порог и ожидает ValueError; '
        'negative-gate.json отдельно подтверждает отказ на повреждённых ответах.', '',
        'Доказательства перечислены по созданным артефактам. Сам факт генерации этого отчёта '
        'не означает прохождения tests/check.py; итог 9/9 нужно получить отдельной проверкой.', '',
    ]
    (docs / 'defects.md').write_text('\n'.join(defects), encoding='utf-8')
    print('Сохранены docs/comparison.csv, docs/conclusion.md и docs/defects.md; нужен ручной разбор пяти пар.')


if __name__ == '__main__':
    main()
