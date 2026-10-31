.DEFAULT_GOAL := help
COMPOSE := docker compose

.PHONY: help up down status notebook test airflow dags-check carregar localidades dbt transformar

help: ## lista os comandos
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  \033[36mmake %-12s\033[0m %s\n", $$1, $$2}'

.env:
	cp .env.example .env

up: .env ## sobe os containers e espera ficarem saudáveis
	$(COMPOSE) up -d --wait
	@$(MAKE) --no-print-directory status

airflow: .env ## sobe banco + Airflow (UI em localhost:8080)
	$(COMPOSE) --profile airflow up -d --build --wait
	@$(MAKE) --no-print-directory status

dags-check: ## confere se as DAGs importam sem erro (no container)
	$(COMPOSE) --profile airflow run --rm --no-deps airflow-dag-processor airflow dags list-import-errors

carregar: ## dispara a malha municipal; EDICAO=2019 para backfill
	$(COMPOSE) exec airflow-apiserver airflow dags trigger ibge_malha_municipal $(if $(EDICAO),-c '{"edicao": $(EDICAO)}')

localidades: ## dispara a coleta da API Localidades
	$(COMPOSE) exec airflow-apiserver airflow dags trigger ibge_localidades

dbt: ## dbt build local (staging → marts) contra o banco do compose
	cd dbt && uv run dbt build --profiles-dir .

transformar: ## dispara a DAG dbt_geo (Cosmos) no Airflow
	$(COMPOSE) exec airflow-apiserver airflow dags trigger dbt_geo

down: ## para os containers (mantém os dados)
	$(COMPOSE) --profile '*' down

status: ## painel dos serviços
	@uv run --quiet scripts/status.py

notebook: ## abre o notebook de exploração das fontes (marimo)
	uv run marimo edit notebooks/01_explorar_fontes.py

test: ## roda os testes (pytest)
	uv run pytest
