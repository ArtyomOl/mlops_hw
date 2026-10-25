"""Строгая оценка MCQ и допуск без регрессий (лекция 7, слайды 2–3, 7–11)."""
import json
import math


def _require(condition, reason):
    if not condition:
        raise ValueError(reason)


def _indexed(items, name):
    _require(isinstance(items, list) and bool(items), f'{name}: нужен непустой список')
    index = {}
    for item in items:
        _require(isinstance(item, dict), f'{name}: строка должна быть объектом')
        key = item.get('id')
        _require(isinstance(key, str) and bool(key.strip()), f'{name}: нужен строковый id')
        _require(key not in index, f'{name}: повтор id {key}')
        index[key] = item
    return index


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Повтор JSON-поля {key}')
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError(f'Недопустимая JSON-константа {value}')


def _parse(raw):
    if not isinstance(raw, str):
        return None
    try:
        return json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except (ValueError, RecursionError):
        return None


def _counts(items):
    n = len(items)
    _require(n > 0, 'Нельзя считать метрики на пустой группе')
    correct = sum(item['correct'] for item in items)
    valid = sum(item['valid'] for item in items)
    errors = sum(item['error'] is not None for item in items)
    return dict(n=n, correct=correct, valid=valid, errors=errors,
                accuracy=correct / n, format_rate=valid / n)


def score(rows, outputs):
    """Сопоставить по id; каждый вопрос остаётся в знаменателе и per_item."""
    questions = _indexed(rows, 'rows')
    answers = _indexed(outputs, 'outputs')
    _require(questions.keys() == answers.keys(), 'Не совпадают id заданий и ответов')
    items, groups = [], {}
    for key, row in questions.items():
        choices, slices = row.get('choices'), row.get('slices')
        _require(isinstance(choices, list) and bool(choices)
                 and all(isinstance(c, str) and c for c in choices), f'{key}: некорректные choices')
        _require(len(choices) == len(set(choices)) and row.get('expected') in choices,
                 f'{key}: некорректный expected или повтор choices')
        _require(isinstance(slices, list) and bool(slices)
                 and all(isinstance(s, str) and s.strip() for s in slices), f'{key}: нужны slices')
        _require(len(slices) == len(set(slices)), f'{key}: повтор среза')
        output = answers[key]
        _require('raw' in output and 'error' in output, f'{key}: нужны raw и error')
        raw, error = output['raw'], output['error']
        _require(error is None or (isinstance(error, str) and bool(error)), f'{key}: некорректный error')
        parsed = _parse(raw)
        valid = (error is None and isinstance(parsed, dict) and set(parsed) == {'answer'}
                 and isinstance(parsed['answer'], str) and parsed['answer'] in choices)
        item = dict(id=key, raw=raw, parsed=parsed, valid=valid,
                    correct=valid and parsed['answer'] == row['expected'], error=error, slices=list(slices))
        items.append(item)
        for name in slices:
            groups.setdefault(name, []).append(item)
    return dict(overall=_counts(items), slices={name: _counts(group) for name, group in sorted(groups.items())},
                per_item=items)


def _validate_counts(actual, expected, name):
    _require(isinstance(actual, dict), f'{name}: нет метрик')
    for key in ('n', 'correct', 'valid', 'errors'):
        value = actual.get(key)
        _require(type(value) is int and value == expected[key], f'{name}: некорректный count {key}')
    for key in ('accuracy', 'format_rate'):
        value = actual.get(key)
        _require(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1,
                 f'{name}: missing/NaN/Inf в {key}')
        _require(math.isclose(value, expected[key], rel_tol=0, abs_tol=1e-12),
                 f'{name}: {key} не соответствует counts')


def _validate_report(report, name, minimum):
    _require(isinstance(report, dict), f'{name}: нужен отчёт')
    items = _indexed(report.get('per_item'), name + '.per_item')
    _require(len(items) >= minimum, f'{name}: нужно минимум {minimum} примеров')
    groups = {}
    for key, item in items.items():
        _require({'raw', 'parsed', 'valid', 'correct', 'error', 'slices'} <= item.keys(),
                 f'{name}/{key}: неполная строка')
        _require(type(item['valid']) is bool and type(item['correct']) is bool,
                 f'{name}/{key}: valid/correct должны быть bool')
        _require(not item['correct'] or item['valid'], f'{name}/{key}: correct требует valid')
        _require(item['error'] is None, f'{name}/{key}: ошибка генерации: {item["error"]}')
        parsed = _parse(item['raw'])
        _require(parsed == item['parsed'], f'{name}/{key}: parsed не соответствует raw')
        if item['valid']:
            _require(isinstance(parsed, dict) and set(parsed) == {'answer'}
                     and isinstance(parsed['answer'], str), f'{name}/{key}: некорректный JSON')
        slices = item['slices']
        _require(isinstance(slices, list) and bool(slices)
                 and all(isinstance(s, str) and bool(s.strip()) for s in slices), f'{name}/{key}: нет срезов')
        _require(len(slices) == len(set(slices)), f'{name}/{key}: повтор среза')
        for s in slices:
            groups.setdefault(s, []).append(item)
    _validate_counts(report.get('overall'), _counts(list(items.values())), name + '.overall')
    _require(isinstance(report.get('slices'), dict) and report['slices'].keys() == groups.keys(),
             f'{name}: имена срезов не соответствуют per_item')
    for s, group in groups.items():
        _validate_counts(report['slices'][s], _counts(group), f'{name}.slices.{s}')
    return items


def _same_population(first, second, name):
    _require(first.keys() == second.keys(), f'{name}: различаются id')
    for key in first:
        _require(set(first[key]['slices']) == set(second[key]['slices']), f'{name}/{key}: изменились срезы')


def quality_gate(baseline, candidate, critical_slices):
    """PASS лишь для совместимых полных отчётов без допустимой регрессии."""
    _require(isinstance(baseline, dict) and isinstance(candidate, dict), 'Нужны два отчёта')
    for key in ('protocol_sha256', 'golden_sha256', 'baseline_spec_sha256'):
        _require(isinstance(baseline.get(key), str) and bool(baseline[key])
                 and baseline[key] == candidate.get(key), f'Несовместимый или отсутствующий {key}')
    validated = []
    for name, report in [('baseline', baseline), ('candidate', candidate)]:
        _require(report.get('status') == 'complete', f'{name}: оценка не завершена')
        _require(isinstance(report.get('model'), dict) and bool(report['model'])
                 and isinstance(report['model'].get('kind'), str) and bool(report['model']['kind']),
                 f'{name}: нет спецификации модели')
        model = report['model']
        if model['kind'] == 'base':
            _require(isinstance(model.get('name'), str) and bool(model['name'])
                     and isinstance(model.get('revision'), str) and len(model['revision']) == 40
                     and all(c in '0123456789abcdef' for c in model['revision']), f'{name}: база не закреплена')
        elif model['kind'] == 'adapter':
            _require(all(isinstance(model.get(k), str) and bool(model[k]) for k in ('name', 'version', 'run_id', 'uri')),
                     f'{name}: неполная версия адаптера')
            _require(model['version'].isdigit() and int(model['version']) > 0
                     and model['uri'] == f'models:/{model["name"]}/{model["version"]}',
                     f'{name}: требуется URI конкретной версии')
        else:
            # Этот kind используется тестами преподавателя; загрузчик его не поддерживает.
            _require(model['kind'] == 'fixture', f'{name}: неизвестный kind модели')
        items = _validate_report(report, name, 50)
        _require(len(report['slices']) >= 3, f'{name}: нужно минимум три среза')
        behavior = _validate_report(report.get('behavioral'), name + '.behavioral', 3)
        validated.append((items, behavior))
    _same_population(validated[0][0], validated[1][0], 'golden')
    _same_population(validated[0][1], validated[1][1], 'behavioral')
    _require(isinstance(critical_slices, list) and bool(critical_slices)
             and all(isinstance(s, str) and bool(s.strip()) for s in critical_slices), 'Нужны критические срезы')
    _require(len(critical_slices) == len(set(critical_slices)), 'Повтор критического среза')
    for key in ('accuracy', 'format_rate'):
        _require(candidate['overall'][key] >= baseline['overall'][key], f'Регрессия общей {key}')
    for name in critical_slices:
        _require(name in baseline['slices'] and name in candidate['slices'], f'Нет критического среза {name}')
        _require(candidate['slices'][name]['accuracy'] >= baseline['slices'][name]['accuracy'],
                 f'Регрессия критического среза {name}')
    _require(all(item['correct'] for item in validated[1][1].values()), 'Обязательные behavioral-кейсы не пройдены')
    return dict(passed=True, protocol_sha256=candidate['protocol_sha256'],
                golden_sha256=candidate['golden_sha256'], baseline_spec_sha256=candidate['baseline_spec_sha256'],
                baseline_model=baseline['model'], candidate_model=candidate['model'],
                critical_slices=list(critical_slices), allowed_regression=0,
                baseline_overall=baseline['overall'], candidate_overall=candidate['overall'],
                behavioral_passed=len(validated[1][1]))
