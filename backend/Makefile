# AI Solution Builder — Backend Makefile
# Convenience targets for lint, type-check, tests, migrations, Docker, and security.

PYTHON ?= .venv/bin/python
PIP    ?= .venv/bin/pip
ifeq ($(OS),Windows_NT)
    PYTHON ?= .venv\Scripts\python.exe
    PIP    ?= .venv\Scripts\pip.exe
endif

.PHONY: help install lint format type test test-unit test-integration coverage \
        migrate makemigration seed docker-build docker-up security run

help:
	@echo "Targets:"
	@echo "  install         Install dev dependencies"
	@echo "  lint            Run ruff check"
	@echo "  format          Run ruff format"
	@echo "  type            Run mypy on app/"
	@echo "  test            Run full pytest suite with coverage"
	@echo "  test-unit       Run tests/unit only"
	@echo "  test-integration Run tests/integration only"
	@echo "  coverage        Print coverage report"
	@echo "  migrate         Run alembic upgrade head"
	@echo "  makemigration   Autogenerate an alembic migration"
	@echo "  docker-build    Build the backend Docker image"
	@echo "  docker-up       Start postgres + redis via docker compose"
	@echo "  security        Run pip-audit against requirements"
	@echo "  run             Start uvicorn on :8000"

install:
	$(PIP) install -r requirements-dev.txt

lint:
	ruff check .

format:
	ruff format . && ruff check --fix .

type:
	mypy app/

test:
	$(PYTHON) -m pytest tests/ -v

test-unit:
	$(PYTHON) -m pytest tests/unit/ -v

test-integration:
	$(PYTHON) -m pytest tests/integration/ -v

coverage:
	$(PYTHON) -m pytest tests/ --cov-report=term-missing

migrate:
	alembic upgrade head

makemigration:
	alembic revision --autogenerate -m "$(m)"

docker-build:
	docker build -t ai-solution-builder-backend:test .

docker-up:
	docker compose -f ../docker-compose.yml up -d postgres redis

security:
	pip-audit -r requirements.txt

run:
	uvicorn main:app --reload --host 0.0.0.0 --port 8000