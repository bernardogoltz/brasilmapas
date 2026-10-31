.DEFAULT_GOAL := help
COMPOSE := docker compose

.PHONY: help up down status notebook test airflow dags-check carregar localidades censo dbt transformar tiles validar explorador simplificacao benchmark obs tour

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

censo: ## dispara o Censo 2022 intramunicipal (setores, bairros, distritos); FORCAR=1 recarrega
	$(COMPOSE) exec airflow-apiserver airflow dags trigger ibge_censo2022_intramunicipal $(if $(FORCAR),-c '{"forcar": true}')

dbt: ## dbt build local (staging → marts) contra o banco do compose
	cd dbt && uv run dbt build --profiles-dir .

transformar: ## dispara a DAG dbt_geo (Cosmos) no Airflow
	$(COMPOSE) exec airflow-apiserver airflow dags trigger dbt_geo

tiles: .env ## sobe o Martin (vector tiles em localhost:3001)
	$(COMPOSE) --profile core up -d --wait martin

validar: ## valida UFs/municípios com o geoibge; IDS="SP RJ 3550308"
	uv run geoibge validar $(or $(IDS),SP RJ 3550308)

explorador: ## app do explorador: UF → mapa, clique → reverse() (marimo run)
	uv run marimo run notebooks/05_explorador.py

simplificacao: ## notebook de calibração da simplificação (marimo)
	uv run marimo edit notebooks/02_simplificacao.py

benchmark: ## notebook de benchmark do reverse() (marimo)
	uv run marimo edit notebooks/03_benchmark_reverse.py

obs: .env ## sobe Prometheus, exporters e Grafana (localhost:3000) e garante o papel monitor
	$(COMPOSE) up -d --wait postgis
	$(COMPOSE) exec -T postgis bash /docker-entrypoint-initdb.d/02_monitor.sh
	$(COMPOSE) --profile obs up -d --wait
	@$(MAKE) --no-print-directory status

tour: ## notebook final: tour da geoibge, do dado ao mapa (marimo)
	uv run marimo edit notebooks/06_tour.py

down: ## para os containers (mantém os dados)
	$(COMPOSE) --profile '*' down

status: ## painel dos serviços
	@uv run --quiet scripts/status.py

notebook: ## abre o notebook de exploração das fontes (marimo)
	uv run marimo edit notebooks/01_explorar_fontes.py

test: ## roda os testes (pytest)
	uv run pytest
