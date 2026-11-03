"""Закрепить протокол и обоснование критических срезов ДО генерации ответов."""
from datetime import datetime, timezone
from pathlib import Path

from evaluation.cli import candidate_model, inputs
from evaluation.contract import fingerprint, write_json


RATIONALE = {
    'numeric': 'Точные числа определяют правильность ответа; близкая формулировка не исправляет ошибочное число.',
    'method': 'Выбор архитектуры или метода — основное содержание вопросов по NLP-статьям.',
    'dataset': 'Проверяет правильность определения источника и состава данных.',
    'metric': 'Проверяет понимание того, как авторы измеряли результат.',
}


def main():
    path = Path('docs/protocol.json')
    if path.exists() or Path('metrics/baseline-outputs.json').exists() or Path('metrics/candidate-outputs.json').exists():
        raise ValueError('Протокол уже закреплён или ответы уже получены; не меняйте условия после измерения')
    cfg, rows, behavioral, baseline, proof, protocol_hash = inputs()
    candidate = candidate_model()
    value = dict(created_at=datetime.now(timezone.utc).isoformat(), protocol_sha256=protocol_hash,
                 golden_sha256=fingerprint(rows), baseline_spec_sha256=fingerprint(baseline),
                 baseline=baseline, candidate=candidate, config=cfg, leakage=proof,
                 slice_rationale=RATIONALE, allowed_regression=0,
                 n_golden=len(rows), n_behavioral=len(behavioral),
                 note='Бывший test ДЗ 3 используется как regression golden; независимый audit не проводился. '
                      'AI-проверка разметки не является подтверждением человеком.')
    write_json(path, value)
    text = ['# ДЗ 6+7: протокол до оценки', '',
            f'Зафиксирован {value["created_at"]}. SHA256 протокола: `{protocol_hash}`.', '',
            f'Golden: {len(rows)} вопросов. Behavioral: {len(behavioral)} кейса. '
            f'Критические срезы: {", ".join(cfg["critical_slices"])}. Допуск регрессии: 0.', '']
    for name, reason in RATIONALE.items():
        text.append(f'- {name}: {reason}')
    text.extend(['', 'Один system prompt, seed, do_sample=False, max_new_tokens и scorer для обеих версий. '
                 'Expected не передаётся модели. Accuracy и format rate не ниже baseline; accuracy '
                 'критических срезов не ниже baseline; все обязательные behavioral-кейсы пройдены. '
                 'Несовместимость, неполнота, NaN или ошибка генерации дают отказ.', '',
                 'Реальные ответы ещё не получены. Итоговые метрики будут добавлены после оценки. '
                 'Полный закреплённый протокол сохранён в docs/protocol.json.', ''])
    conclusion = Path('docs/conclusion.md')
    if conclusion.exists():
        raise ValueError('Не перезаписываем существующий вывод предварительным протоколом')
    conclusion.write_text('\n'.join(text), encoding='utf-8')
    print('Протокол, нулевой допуск и причины выбора критических срезов закреплены до оценки')


if __name__ == '__main__':
    main()
