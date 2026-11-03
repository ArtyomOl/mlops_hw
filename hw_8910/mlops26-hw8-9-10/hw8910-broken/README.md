# ДЗ 8–10: выпуск модели и API

Подробный отчёт — [REPORT.md](REPORT.md). Исходный прототип — `original/`; приложенный тест `tests/test_release.py` не менялся.

## Быстрый запуск

Нужен Python 3.12/3.13 и локальные сокеты. Установить зависимости Prefect/FastAPI в отдельное окружение:

```bash
uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python -r requirements-lock.txt
make check
make check-fastapi
```

`python3 evidence/run_checks.py` сохраняет красный прогон исходника и зелёные прогоны исправленных сервисов. `.venv/bin/python evidence/run_flow.py` воспроизводит восстановление и инвалидацию кеша. `.venv/bin/python evidence/run_real_flow.py` запускает настоящий gate на ранее сохранённой оценке; ожидаемый результат текущего кандидата — отказ.

## Доступ к весам

Файлы из ДЗ 6–7 хранятся локально, в архив и Git не включаются. Здесь они уже восстановлены в `artifacts/candidate/`, а база хранится в Hugging Face cache. Для восстановления адаптера с того же хоста из ранее созданного volume MLflow:

```bash
podman machine start
podman start mlops-hw6-mlflow-1
mkdir -p artifacts
podman cp mlops-hw6-mlflow-1:/mlartifacts/1/94a484907fdd4275ab911cb26b7eec06/artifacts/model/artifacts/adapter ./artifacts/candidate
```

Копия должна содержать `adapter_model.safetensors`, `adapter_config.json`, токенизатор, шаблон и `manifest.json`; flow сверяет их хеши. Для преподавателя нужен доступ к этому MLflow artifact или отдельная передача тех же файлов вне архива. Базовую `Qwen/Qwen3-0.6B` необходимо получить с ревизией `c1899de289a04d12100db370d81485cdf75e47ca`. Если расположение базы изменилось, `python3 prepare_real.py --rebind-baseline` обновит её путь только после совпадения хешей модели и runtime; принятую другую модель команда не перезапишет. `inputs67/` уже содержит данные и отчёты оценки.

Реальный API использует окружение из ДЗ 6–7, где установлены PyTorch, Transformers, PEFT и FastAPI. Запуск: `../../../hw_SIXSEVEN/mlops26-hw6-7/hw67-broken/.venv/bin/python api.py --workspace real-baseline --backend real --port 8091`. Локальный сервис работает только на `127.0.0.1`.
