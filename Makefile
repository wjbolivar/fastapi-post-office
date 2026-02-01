# -----------------------------
# FastAPI Post Office - Makefile
# Always uses local .venv
# -----------------------------

VENV_DIR ?= .venv
PYTHON ?= $(VENV_DIR)/bin/python
PIP ?= $(PYTHON) -m pip
PYTEST ?= $(PYTHON) -m pytest
RUFF ?= $(PYTHON) -m ruff
BLACK ?= $(PYTHON) -m black
MYPY ?= $(PYTHON) -m mypy

# If python3 isn't available, users will see a clear error.
SYSTEM_PYTHON ?= python3

.PHONY: help venv upgrade-pip install lint format fmt-check typecheck test coverage clean

help:
	@echo "Targets:"
	@echo "  venv         Create .venv and install pip"
	@echo "  install      Install dev dependencies into .venv"
	@echo "  lint         Run ruff"
	@echo "  format       Run black formatter"
	@echo "  fmt-check    Check formatting"
	@echo "  typecheck    Run mypy"
	@echo "  test         Run pytest"
	@echo "  coverage     Run pytest with coverage"
	@echo "  clean        Remove caches"

# Create venv if missing
$(VENV_DIR)/bin/python:
	$(SYSTEM_PYTHON) -m venv $(VENV_DIR)

venv: $(VENV_DIR)/bin/python
	@echo "✅ Virtualenv ready at $(VENV_DIR)"

upgrade-pip: $(VENV_DIR)/bin/python
	$(PIP) install -U pip

install: venv upgrade-pip
	$(PIP) install -e ".[dev,smtp,celery,admin]"

lint: venv
	$(RUFF) check fastapi_post_office tests

format: venv
	$(BLACK) fastapi_post_office tests

fmt-check: venv
	$(BLACK) --check fastapi_post_office tests

typecheck: venv
	$(MYPY) fastapi_post_office

test: venv
	$(PYTEST)

coverage: venv
	$(PYTEST) --cov=fastapi_post_office --cov-report=term-missing

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
