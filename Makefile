.DEFAULT_GOAL := help
COMPOSE := docker compose

.PHONY: help up down status notebook

help: ## lista os comandos
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  \033[36mmake %-10s\033[0m %s\n", $$1, $$2}'

.env:
	cp .env.example .env

up: .env ## sobe os containers e espera ficarem saudáveis
	$(COMPOSE) up -d --wait
	@$(MAKE) --no-print-directory status

down: ## para os containers (mantém os dados)
	$(COMPOSE) down

status: ## painel dos serviços
	@uv run --quiet scripts/status.py

notebook: ## abre o notebook de exploração das fontes (marimo)
	uv run marimo edit notebooks/01_explorar_fontes.py
