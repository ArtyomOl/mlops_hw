PYTHON ?= python3
PYTHON_VERSION ?= 3.13
VENV ?= .venv
B_RESULTS ?= results/b
C_RESULTS ?= results/c
KUBE_BIN := $(CURDIR)/.tools
export PATH := $(KUBE_BIN):$(PATH)
export KUBECONFIG ?= $(CURDIR)/.state/kubeconfig

.PHONY: check setup stand footprint exp-a exp-b exp-c report clean-stand

setup:
	@test -x $(VENV)/bin/python || uv venv --python $(PYTHON_VERSION) $(VENV)
	uv pip sync --python $(VENV)/bin/python requirements-dev.txt

check:
	$(VENV)/bin/python -m unittest discover -s tests -v

exp-a:
	$(PYTHON) experiments/experience_a.py

report:
	$(VENV)/bin/python scripts/build_report.py

stand:
	./scripts/up.sh

footprint:
	./scripts/footprint.sh

exp-b:
	$(PYTHON) experiments/experiment_b.py --resume --out $(B_RESULTS)

exp-c:
	$(PYTHON) experiments/experiment_c.py --out $(C_RESULTS) $(EXP_C_ARGS)
	$(PYTHON) experiments/compare_histograms.py --results $(C_RESULTS) $(EXP_C_ARGS)

clean-stand:
	./scripts/down.sh
