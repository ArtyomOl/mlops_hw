"""Локальный комплект сдачи: код, отчёты и данные оценки без весов и окружения."""
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def main():
    root = Path(__file__).resolve().parents[1]
    required = ['docs/comparison.csv', 'docs/defects.md', 'docs/conclusion.md', 'docs/protocol.json',
                'metrics/baseline-outputs.json', 'metrics/candidate-outputs.json',
                'metrics/baseline-eval.json', 'metrics/candidate-eval.json', 'metrics/eval-diff.json',
                'metrics/quality-gate.json', 'metrics/negative-gate.json', 'metrics/storage-check.json',
                'metrics/acceptance.log', 'evaluation/baseline.json', 'dvc.lock',
                'data/eval/golden.jsonl', 'data/eval/behavioral.jsonl', 'data/eval/training-index.jsonl']
    missing = [name for name in required if not (root / name).is_file()]
    if missing:
        raise ValueError(f'Не хватает обязательных артефактов: {missing}')
    patterns = ['src/*.py', 'evaluation/*.py', 'evaluation/*.json', 'scripts/*.py', 'tests/*',
                'examples/*.jsonl', 'docs/*.md', 'docs/*.json', 'docs/*.csv', 'metrics/*.json', 'metrics/*.log',
                'metrics/evaluation-history/**/*.json', 'metrics/evaluation-history/**/*.md',
                'metrics/evaluation-history/**/*.py', 'data/eval/*']
    fixed = ['Makefile', 'Dockerfile', '.dockerignore', '.gitignore', 'compose.yaml', 'params.yaml',
             'pyproject.toml', 'uv.lock', 'dvc.yaml', 'dvc.lock', 'README.md', 'EVALUATION.md']
    files = {root / name for name in fixed}
    for pattern in patterns:
        files.update(p for p in root.glob(pattern) if p.is_file() and not p.is_symlink())
    test_hash = hashlib.sha256()
    for p in sorted((root / 'tests').iterdir()):
        if p.is_file():
            test_hash.update(p.name.encode())
            test_hash.update(p.read_bytes())
    checksums = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted(files)}
    gate = json.loads((root / 'metrics/quality-gate.json').read_text())
    manifest = dict(files_sha256=checksums, tests_fingerprint=test_hash.hexdigest()[:12],
                    quality_gate=gate, git_commit_created=False,
                    excluded=['model weights', 'training tensors', '.venv', 'container volumes', 'DVC cache'],
                    remaining=['Проверка разметки человеком', 'Одно видео 5–8 минут'])
    readme = (
        '# Локальный комплект ДЗ 6+7\n\n'
        'Итог — docs/conclusion.md; шесть runs — docs/comparison.csv; причины исправлений — docs/defects.md.\n'
        'В metrics/ лежат реальные ответы, per-item отчёты, diff, решения gate и проверки хранения/приёмки.\n'
        'Данные проверки приложены непосредственно в data/eval/ для доступа преподавателю; '
        'их DVC-хеши находятся в dvc.lock. Исходные обучающие тензоры и веса не входят в архив.\n\n'
        'Весь репозиторий продолжает ДЗ 3–5: пути обучения ведут в hw4/hw4-broken/data/tokenized. '
        'Локальное DVC-хранилище dvc_remote находится в корне mlops_hw и не публиковалось. '
        'Для переноса данных оценки достаточно этого приложения. Baseline закреплён в evaluation/baseline.json.\n\n'
        'Ссылки на MLflow указывают на локальный сервер автора; отчёты приложены также файлами. '
        'Git-коммит по указанию пользователя не создавался. '
        'Разметка имеет статус human_review=pending; AI-проверку нельзя выдавать за человеческую. '
        'Видео не записано и должно быть добавлено отдельно.\n'
    )
    destination = root / 'submission'
    destination.mkdir(exist_ok=True)
    output = destination / 'hw67-local.zip'
    with ZipFile(output, 'w', compression=ZIP_DEFLATED) as archive:
        for p in sorted(files):
            archive.write(p, p.relative_to(root).as_posix())
        archive.writestr('SUBMISSION_README.md', readme)
        archive.writestr('submission-manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    with ZipFile(output) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise ValueError(f'Повреждён файл архива: {bad}')
    print(f'{output}: {len(files)} файлов, {output.stat().st_size} байт; tests={manifest["tests_fingerprint"]}')


if __name__ == '__main__':
    main()
