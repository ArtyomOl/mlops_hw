# ДЗ 11. Kubernetes под нагрузкой

Продолжение ДЗ 8–10. FastAPI сохраняет `/health`, `/ready` и `POST /generate`, `request_id`, `model_id` и строгую валидацию. Ответ передаётся частями в NDJSON. Поле `backend_mode=simulated` обозначает CPU-имитатор. Поддерживаемое для совместимости поле `max_new_tokens` задаёт число частей. В опытах используется явное поле `parts`.

[Условие](homework11.html) · [Отчёт](report.html) · [Дашборд Grafana](chart/files/dashboard.json)

## Запуск

Нужны Python 3.13, `uv`, kind 0.30.0, kubectl 1.34.0, Helm 3.19.0 и контейнерный движок. Скрипты также ищут CLI в `.tools/`. На macOS с Podman 5.7.1 сначала запусти существующую VM через `podman machine start`. Для Docker укажи `KIND_EXPERIMENTAL_PROVIDER=docker` при создании и удалении стенда.

```sh
cd hw_11
make setup
make check
make stand
./scripts/check_monitoring.sh
```

`make stand` создаёт kind `hw11`, собирает образ, загружает его в узел и устанавливает чарт и Metrics Server. Kubeconfig хранится в `.state/kubeconfig`. Артефакты A/B входят в образ, а хеши в [`chart/values.yaml`](chart/values.yaml) сверяются с файлами в [`models/`](models/). Для реальных весов понадобится версионированное хранилище, доступное всем репликам, например объектное хранилище или RWX-том при многоузловом размещении.

```sh
make exp-a   # прогрев, rollout, откат, авария и замена Pod
make exp-b   # два Service и два профиля трафика, по три прогона
make exp-c   # HPA и два алерта
make report  # results/requests.jsonl, SVG и report.html
```

Последовательный B занимает около получаса и пропускает уже завершённые серии. Для нового B укажи `make exp-b B_RESULTS=results/b-repeat`. Для параллельного воспроизведения отдельных блоков B на одном узле используй `PATH="$PWD/.tools:$PATH" KUBECONFIG="$PWD/.state/kubeconfig" python3 experiments/experiment_b_parallel.py`. У каждого блока свой Deployment с двумя Service и отдельными клиентами. Для повторного C укажи новый каталог: `make exp-c C_RESULTS=results/c-repeat EXP_C_ARGS="--namespace hw11-c-repeat"`. Основные результаты лежат в `results/`.

Для просмотра Grafana:

```sh
export PATH="$PWD/.tools:$PATH"
export KUBECONFIG="$PWD/.state/kubeconfig"
kubectl -n hw11 get pods,endpointslice
kubectl -n hw11 port-forward svc/hw11-grafana 3000:3000
```

Открой `http://127.0.0.1:3000`. Для C создаётся `hw11-c` со своим Prometheus и без второго Grafana, для A — `hw11-a`.

```sh
make footprint
make clean-stand
```

Удаление очищает кластер `hw11` с временными томами. `./scripts/down.sh --remove-image` дополнительно удаляет образ задания. Снимки `results/platform-before.txt` и `results/platform-after.txt` показывают ресурсы до и после запуска. На старте было около 289 GiB свободного места на macOS и 76,6 GiB в VM. Стартовые лимиты VM — 6 CPU, 2 GiB RAM и 100 GiB виртуального диска. При одновременном запуске нескольких опытов увеличение до 4 GiB устранило OOM; журнал находится в [`results/platform-vm-resize.txt`](results/platform-vm-resize.txt). Чтобы вернуть исходный лимит после удаления стенда, останови VM командой `podman machine stop podman-machine-default` и выполни `podman machine set --memory 2048 podman-machine-default`.
