# Сценарий видео ДЗ 6–7 — примерно 7–8 минут

Сервисы уже запущены: Podman, Postgres и MLflow. Интерфейс: http://127.0.0.1:5006.
Для записи используем сохранённые шесть обучений и реальные ответы двух версий.
Команды ниже выполняются в обычном терминале во время записи; сейчас повторное обучение и оценка не запускались.

## Подготовка терминала до записи

```bash
cd /Users/artyom-olenev/Projects/mlops_hw/hw_SIXSEVEN/mlops26-hw6-7/hw67-broken
export PATH="/opt/homebrew/bin:$PATH"
export DOCKER_CONFIG=/private/tmp/mlops-hw67-docker
export DOCKER_HOST="unix://$(podman machine inspect --format '{{.ConnectionInfo.PodmanSocket.Path}}' podman-machine-default)"
export HF_HUB_OFFLINE=1
set -o pipefail
```

Временная конфигурация Docker для установленного Compose уже подготовлена.
Открой в редакторе перечисленные ниже файлы заранее, чтобы не тратить видео на поиск.

## 0:00–0:30. Цель и сервисы

Скажи: «Продолжил ДЗ 4–5: вопросы по evidence из NLP-статей, Qwen3-0.6B,
шесть LoRA-конфигураций, выбор по val loss и отдельная проверка качества ответов».

```bash
docker compose -p mlops-hw6 ps
```

Покажи работающие `db` и `mlflow`. В `compose.yaml` покажи отдельные volumes
для Postgres и артефактов. `:Z` обеспечивает relabel при пересоздании контейнера в Podman/SELinux.

## 0:30–1:50. Шесть runs и четыре исправления

Открой эксперимент `hw6-lora`: http://127.0.0.1:5006/#/experiments/1.
Фильтр `tags.kind = 'candidate'` оставляет шесть обучающих runs.
Покажи FINISHED, r, lr, target_modules, final_val_loss, seconds, peak_memory_mb и adapter_mb.
Те же измерения находятся в `docs/comparison.csv`.

Лучший run:
http://127.0.0.1:5006/#/experiments/1/runs/94a484907fdd4275ab911cb26b7eec06.

Покажи его кривую `val_loss` на шагах 0, 2, 4, Params и Tags с версиями.
Проговори: `all-r8-high`, r=8, lr=0.0003, семь проекций; loss 0.9496 → 0.4675.
Бюджет у всех одинаковый: 4 шага, train-пул 32, val 8, batch 1 × accumulation 2, seed 42.
Ресурсы измерены короткими прогонами; первый включает прогрев, память MPS включает кеши драйвера.

Кратко покажи `docs/defects.md` и нужные участки кода:

- `src/sweep.py`: отдельный nested run для каждого кандидата; полный provenance с хешами train/val.
- `compose.yaml`: постоянный artifact volume.
- `src/promote.py`: `gate(run, threshold)` выполняется до регистрации и назначения alias.

Четыре исправления: смешивание runs; потеря артефактов; отбрасывание версий данных; обход loss-порога.

## 1:50–2:30. Реестр и пакет модели

В MLflow открой Models → `my-qwen-adapter` → версия 1.
Покажи alias `candidate`, отсутствие `champion` и теги `quality.validation=rejected` и `quality.evaluation_run_id`.
Тег `validation=passed` относится к loss-порогу части A; качество ответов проверяется отдельно.
Отношение val/base равно примерно 0.4923 при пороге 1.0.

В Artifacts выбранного обучающего run покажи пакет `model`: MLmodel с signature/input example,
адаптер, tokenizer, manifest и MODEL_CARD.md. В `evaluation/baseline.json` покажи базу с точной ревизией.

## 2:30–3:30. Данные и протокол

```bash
wc -l data/eval/golden.jsonl data/eval/behavioral.jsonl data/eval/training-index.jsonl
../../../hw3/hw3-broken/.venv/bin/dvc status dvc.yaml
```

Ожидаются 50 golden-примеров, 4 behavioral-кейса, 1421 исходный train-вопрос и актуальный DVC-пайплайн.
В редакторе покажи:

- `data/eval/golden.jsonl`: один пример с id, group_id, input, expected, choices, slices и source.
- `data/eval/provenance.json`: хеши исходников/тензоров, связь с ДЗ 4, отсутствие точных/group-пересечений.
- `data/eval/behavioral.jsonl`: format, paraphrase, refusal и insufficient evidence.
- `evaluation/params.json` и `docs/protocol.json`: одинаковые условия для двух версий, seed=42,
  max_new_tokens=32, thinking=false, критические numeric/method и допуск регрессии 0.
- `dvc.lock`: версия набора.

Скажи: «Срезы — dataset, method, metric, numeric. Числа и методы критичны.
Expected не передавался модели. Бывший test ДЗ 3 используется как регрессионный golden;
независимым финальным аудитом это не является. Проверка совпадений не исключает все смысловые утечки».

Статус человеческой проверки разметки сейчас `pending`. Не называй его завершённой ручной проверкой,
если сам ещё не сверил вопросы и эталоны с evidence.

## 3:30–4:40. Реальные ответы и срезы

Открой итоговый оценочный run:
http://127.0.0.1:5006/#/experiments/2/runs/aa00d482199544e1aa299cf11aa31d68.
В Artifacts → evaluation покажи raw outputs, per-item отчёты и eval-diff.

Для компактного вывода метрик в терминале:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path
for role in ("baseline", "candidate"):
    report = json.loads(Path(f"metrics/{role}-eval.json").read_text())
    print(role, report["overall"])
    for name, metrics in report["slices"].items():
        print(" ", name, metrics)
    print("behavioral", report["behavioral"]["overall"])
PY
```

Основные числа:

- База: accuracy 49/50 = 98%, format rate 50/50 = 100%.
- Кандидат: accuracy 0/50, format rate 0/50; генерация завершилась без аварий.
- Numeric у базы 9/10, method 15/15, dataset 20/20, metric 5/5. У кандидата все эти counts равны нулю.
- Behavioral: база 3/4, кандидат 0/4. Исправленных ответов нет, потеряно 49.

В `docs/conclusion.md` покажи хотя бы три разобранные пары:

- `qasper-mcq-001`: правильный выбор A, у базы JSON, у кандидата голая A → нарушение схемы.
- `qasper-mcq-029`: 657 — число оценок, 14 — число добровольцев. Верен B, обе версии выбирают A;
  база дополнительно показывает, что валидный формат не гарантирует правильности факта.
- `qasper-mcq-050`: верен B = 1.3 million words; у кандидата снова отсутствует JSON.

Ещё две пары, 004 и 046, уже включены в отчёт. Ноль по строгому контракту не означает,
что все содержательные варианты неверны: каждое нарушение JSON получает нулевой end-to-end score.

## 4:40–5:20. Отказ выпуска и отрицательный тест

В `evaluation/solution.py` покажи `score` и `quality_gate`: единственное поле answer,
все вопросы в знаменателе, проверка counts/конечности/совместимости и отсутствие допустимой регрессии.

```bash
make eval
cat metrics/quality-gate.json
make check-negative
cat metrics/negative-gate.json
```

`make eval` намеренно завершится с ненулевым кодом и сообщением «Регрессия общей accuracy».
Это ожидаемый отказ кандидату. После него следующую команду запускай отдельно.
`make check-negative` должен вывести PASS: испорчена копия ответов; веса и aliases не меняются.
`make promote` при этом результате не выполняется.

## 5:20–6:10. Хранение после пересоздания

```bash
make check-storage
cat metrics/storage-check.json
```

Во время ожидания объясни: «Записывается случайный probe, запоминается SHA256,
пересоздаётся только контейнер MLflow с сохранением volume, затем файл скачивается и хеш сверяется».
Дождись `PASS: новый контейнер вернул тот же артефакт, SHA256 совпал`.
Это force-recreate, а не обычный restart. Проверка создаст новый storage-probe run.

## 6:10–7:20. Приёмка и итог

```bash
make check-all 2>&1 | tee metrics/acceptance.log
```

Дождись: `Итог: 9/9`, отпечатка `c42ac7788026`, 24 преподавательских и 9 дополнительных тестов с OK.
Проверка 7 один раз загрузит candidate в новом процессе без локального конфига;
она кратковременно использует память модели. Обучение и полная оценка не повторяются.
Остальные тесты оценки используют синтетические фикстуры и не заменяют реальные ответы из предыдущего этапа.

Скажи: «Инфраструктурные проверки подтверждают воспроизводимость пайплайна.
Отдельный quality gate отклоняет текущую модель из-за регрессии формата и accuracy.
Candidate остаётся доступным, champion не назначен. Следующий эксперимент — обучение соблюдению
JSON на отдельном dev-наборе с сохранением порогов и истории baseline».

Заверши ограничениями: короткий sweep и маленький golden не доказывают устойчивого преимущества;
BLEU/ROUGE/BERTScore оценивают сходство текста, а не факт; judge полезен для открытых ответов,
но требует рубрики, слепого A/B, перестановки порядка и сверки с человеком. Платный judge не использовался.

## После записи

Поскольку проверка хранения создаёт новый probe, обнови отчёты и архив по свежим файлам:

```bash
make conclusion
make finalize
make submission
```

Локальный архив: `submission/hw67-local.zip`. Само видео добавляется к сдаче отдельно.
Коммит по указанию пользователя не создавался.

Чтобы снова освободить ресурсы:

```bash
docker compose -p mlops-hw6 stop --timeout 30
podman machine stop podman-machine-default
```

Данные, веса, контейнеры и volumes сохраняются.
