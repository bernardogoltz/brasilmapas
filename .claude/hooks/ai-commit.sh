#!/usr/bin/env bash
# Commita o que está staged com mensagem gerada pelo Sonnet 5.5 (effort low).
set -euo pipefail
cd "${CLAUDE_PROJECT_DIR:-.}"
git diff --cached --quiet && { echo "nada staged" >&2; exit 1; }

prompt="Escreva a mensagem de commit para o diff abaixo.
Regras: Conventional Commits em português; título <tipo>(escopo): resumo imperativo ≤72 caracteres; linha em branco; corpo curto explicando o porquê e o que mudou (bullets se houver várias partes), linhas ≤72. Sem Co-Authored-By, sem crases, sem comentários. Responda só com a mensagem.

$(git diff --cached --stat)

$(git diff --cached | head -c 60000)"

msg=$(AUTO_COMMIT_NESTED=1 claude -p --model claude-sonnet-5-5 --effort low <<<"$prompt")
[ -n "$msg" ] || { echo "mensagem vazia" >&2; exit 1; }
git commit -q -F - <<<"$msg"
git log --oneline -1 | cat
