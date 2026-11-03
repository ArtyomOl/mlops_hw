PYTHON ?= python3
.PHONY: check check-fastapi evidence
check:
	$(PYTHON) -m compileall -q release.py lab.py service.py tests
	$(PYTHON) -m unittest discover -s tests -v
check-fastapi:
	SERVICE_SCRIPT=api.py .venv/bin/python -m unittest discover -s tests -v
evidence:
	$(PYTHON) evidence/run_checks.py
