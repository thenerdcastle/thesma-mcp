.PHONY: install test lint format type-check check

install:
	pip install -e ".[dev]"

test:
	pytest tests/ -v --tb=short

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/

format:
	ruff format src/ tests/

type-check:
	mypy src/

check: lint type-check test
