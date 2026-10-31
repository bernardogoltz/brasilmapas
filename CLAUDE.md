# Projeto geo

## Comandos via Makefile

- Toda operação recorrente do projeto vira um alvo no `Makefile`, com comentário `## descrição` (aparece no `make help`).
- A cada iteração que criar algo executável (serviço, DAG, dbt, notebook, testes), adicionar o alvo correspondente no mesmo passo.
- Manter a tabela da seção **Comandos**, no topo do `README.md`, em sincronia com o `Makefile`.
- Saída voltada a humanos (status, resumos) usa `rich`, em scripts de `scripts/` com dependências inline (PEP 723), rodados com `uv run`.
