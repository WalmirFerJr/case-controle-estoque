PY ?= .venv/bin/python
BIN := .venv/bin

.PHONY: help venv install up down db run migrate test test-unit test-integration coverage lint format typecheck arch check

help: ## Lista os comandos disponíveis
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'

venv: ## Cria o ambiente virtual
	python3 -m venv .venv

install: venv ## Instala a aplicação e as dependências de desenvolvimento
	$(BIN)/pip install -e ".[dev]"

up: ## Sobe API + PostgreSQL com Docker (http://localhost:8000/docs)
	docker compose up --build -d

down: ## Derruba os containers
	docker compose down -v

db: ## Sobe apenas o PostgreSQL (para rodar a API localmente)
	docker compose up -d db

migrate: ## Aplica as migrations no banco configurado em STOCK_DATABASE_URL
	$(BIN)/alembic upgrade head

run: ## Roda a API localmente com reload
	$(BIN)/uvicorn stock.main:create_app --factory --reload --port 8000

test: ## Roda todos os testes (sobe um PostgreSQL descartável via Docker)
	$(BIN)/pytest

test-unit: ## Só testes rápidos, sem banco (domínio, casos de uso, property-based)
	$(BIN)/pytest tests/unit tests/property

test-integration: ## Integração + concorrência contra PostgreSQL real
	$(BIN)/pytest -m integration

coverage: ## Testes com relatório de cobertura
	$(BIN)/pytest --cov --cov-report=term-missing

lint: ## Lint e checagem de formatação
	$(BIN)/ruff check src tests
	$(BIN)/ruff format --check src tests

format: ## Formata o código
	$(BIN)/ruff check --fix src tests
	$(BIN)/ruff format src tests

typecheck: ## Tipagem estrita
	$(BIN)/mypy

arch: ## Verifica as regras de dependência da Clean Architecture
	PYTHONPATH=src $(BIN)/lint-imports

check: lint typecheck arch coverage ## Tudo o que o CI roda
