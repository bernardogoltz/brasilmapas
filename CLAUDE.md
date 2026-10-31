# Projeto geo

## Comandos via Makefile

- Toda operação recorrente do projeto vira um alvo no `Makefile`, com comentário `## descrição` (aparece no `make help`).
- A cada iteração que criar algo executável (serviço, DAG, dbt, notebook, testes), adicionar o alvo correspondente no mesmo passo.
- Manter a tabela da seção **Comandos**, no topo do `README.md`, em sincronia com o `Makefile`.
- Saída voltada a humanos (status, resumos) usa `rich`, em scripts de `scripts/` com dependências inline (PEP 723), rodados com `uv run`.

## Testes

- Toda mudança de código (`.py`, `.sql`, `.sh`) vem com teste pytest em `tests/`, no mesmo passo; rodar `make test`.
- Testes sem rede: fixtures pequenas em `tests/fixtures/`. O Stop hook `.claude/hooks/require-tests.sh` cobra isso.
