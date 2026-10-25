"""Сохранить результаты приёмки и состояние реестра; aliases не изменяются."""
import hashlib
from pathlib import Path

from mlflow import MlflowClient

from evaluation.cli import current_reports
from evaluation.contract import read_json, write_json


def main():
    _, candidate = current_reports()
    client = MlflowClient()
    spec = candidate['model']
    registered = client.get_registered_model(spec['name'])
    gate = read_json('metrics/quality-gate.json')
    if registered.aliases.get('candidate') != spec['version']:
        raise ValueError('Alias candidate изменился')
    if not gate['passed'] and registered.aliases.get('champion') == spec['version']:
        raise ValueError('Непринятый кандидат не должен быть champion')
    log = Path('metrics/acceptance.log').read_text(encoding='utf-8')
    if not all(marker in log for marker in ('Итог: 9/9', 'Ran 24 tests', 'Ran 9 tests', 'c42ac7788026')):
        raise ValueError('Журнал не подтверждает полный успешный прогон приёмки')
    h = hashlib.sha256()
    for p in sorted(Path('tests').iterdir()):
        if p.is_file():
            h.update(p.name.encode())
            h.update(p.read_bytes())
    if h.hexdigest()[:12] != 'c42ac7788026':
        raise ValueError('Исходные тесты изменены после приёмки')
    write_json('metrics/registry-state.json', dict(name=registered.name, aliases=registered.aliases,
               candidate=spec, evaluation_run_id=candidate['evaluation_run_id'], quality_passed=gate['passed']))
    write_json('metrics/final-validation.json', dict(mlflow_checks_passed=9, mlflow_checks_total=9,
               provided_tests_passed=24, additional_tests_passed=9, tests_fingerprint=h.hexdigest()[:12],
               quality_gate=gate, storage=read_json('metrics/storage-check.json'),
               negative=read_json('metrics/negative-gate.json'),
               human_review='pending', video='not recorded', git_commit='not created as requested'))
    write_json('docs/runtime-notes.json', dict(
        docker_compose_binary='/opt/homebrew/bin/docker-compose',
        docker_config_for_this_session='/private/tmp/mlops-hw67-docker',
        podman_machine='podman-machine-default',
        compatibility_fixes=[
            'Compose подключён через временный DOCKER_CONFIG без изменения глобального Docker config.',
            '.dockerignore исключает окружение и данные из build context.',
            'Healthcheck использует CMD-SHELL с сохранением quoting Python -c.',
            'Именованные volumes используют :Z: SELinux relabel при пересоздании контейнера.',
        ],
        evaluation_history='metrics/evaluation-history содержит прежние ответы, протоколы и код до исправления '
                           'логирования и генератора отчёта. Модели, prompt, scorer, данные и пороги не менялись.',
        state='candidate доступен; champion не назначен; отказ по качеству — штатный итог работы',
    ))
    paths = ['docs/comparison.csv', 'docs/defects.md', 'docs/conclusion.md', 'docs/protocol.json',
             'docs/pair-review.json', 'docs/runtime-notes.json', 'metrics/acceptance.log',
             'metrics/final-validation.json', 'metrics/registry-state.json', 'metrics/storage-check.json']
    for path in paths:
        client.log_artifact(candidate['evaluation_run_id'], path, 'submission')
    client.set_tag(candidate['evaluation_run_id'], 'quality_gate', 'passed' if gate['passed'] else 'rejected')
    client.set_tag(candidate['evaluation_run_id'], 'acceptance', '9/9; 33 unittest tests')
    client.set_model_version_tag(spec['name'], spec['version'], 'quality.validation',
                                 'passed' if gate['passed'] else 'rejected')
    client.set_model_version_tag(spec['name'], spec['version'], 'quality.evaluation_run_id', candidate['evaluation_run_id'])
    print('Сохранены итоговая приёмка, состояние aliases и отчёты в оценочном run MLflow; aliases не изменялись')


if __name__ == '__main__':
    main()
