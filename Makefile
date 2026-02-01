.PHONY: help install lint format typecheck test coverage clean

help:
	@echo "Available commands:"
	@echo "  install     Install dev dependencies"
	@echo "  lint        Run ruff"
	@echo "  format      Format code with black"
	@echo "  typecheck   Run mypy"
	@echo "  test        Run tests"
	@echo "  coverage    Run tests with coverage report"
	@echo "  clean       Remove cache files"

install:
	pip install -e ".[dev,smtp,celery,admin]"

lint:
	ruff check fastapi_post_office tests

format:
	black fastapi_post_office tests

typecheck:
	mypy fastapi_post_office

test:
	pytest

coverage:
	pytest --cov=fastapi_post_office --cov-report=term-missing

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
