UV ?= uv
VENV ?= .venv
PYTHON := $(VENV)/bin/python

.PHONY: help dev check format format-check lint typecheck test migrate seed reset benchmark openapi

help:  ## Show available targets.
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS=":.*?## "} {printf "  %-14s %s\n", $$1, $$2}'

$(VENV)/bin/python:
	$(UV) venv --system-site-packages --python 3.11 $(VENV)

dev: $(VENV)/bin/python  ## Create the project environment and install dependencies.
	$(UV) pip install --python $(PYTHON) -e ".[dev]" || $(UV) pip install --offline --python $(PYTHON) pytest alembic pyjwt "passlib[bcrypt]" "bcrypt==4.0.1"

check: format-check lint typecheck test  ## Run the full quality gate.

format:  ## Format code with ruff.
	$(PYTHON) -m ruff format app tests alembic

format-check:  ## Check formatting with ruff.
	$(PYTHON) -m ruff format --check app tests alembic

lint:  ## Lint with ruff.
	$(PYTHON) -m ruff check app tests alembic

typecheck:  ## Type-check with mypy (strict on app/).
	$(PYTHON) -m mypy app alembic

test:  ## Run tests (with coverage when pytest-cov is installed).
	if $(PYTHON) -c "import pytest_cov" 2>/dev/null; then $(PYTHON) -m pytest --cov=app --cov-report=term-missing --cov-fail-under=75; else echo "pytest-cov not installed; running tests without coverage"; $(PYTHON) -m pytest; fi

migrate:  ## Apply Alembic migrations to head.
	$(PYTHON) -m alembic upgrade head

seed:  ## Seed demo data (lands in Phase 2).
	echo "Seeding lands in Phase 2 (not implemented yet)." && exit 1

reset:  ## Reset demo data (lands in Phase 6).
	echo "Reset lands in Phase 6 (not implemented yet)." && exit 1

benchmark:  ## Run the evaluation harness (lands in Phase 7).
	echo "Benchmark lands in Phase 7 (not implemented yet)." && exit 1

openapi:  ## Regenerate docs/openapi.json from the app.
	$(PYTHON) -c "import os; from cryptography.fernet import Fernet; os.environ.setdefault('JWT_SECRET', 'openapi-export-only'); os.environ.setdefault('FIELD_ENCRYPTION_KEY', Fernet.generate_key().decode()); import json; from app.main import app; json.dump(app.openapi(), open('docs/openapi.json', 'w', encoding='utf-8'), indent=2)"
