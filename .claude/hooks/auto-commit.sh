#!/usr/bin/env bash
# Stop hook: se houver mudança grande não commitada, pede ao Claude que commite.
input=$(cat)
[ "$(jq -r '.stop_hook_active // false' <<<"$input")" = "true" ] && exit 0
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

MIN_LINES=${AUTO_COMMIT_MIN_LINES:-80}
MIN_FILES=${AUTO_COMMIT_MIN_FILES:-4}

tracked=$(git diff HEAD --numstat 2>/dev/null || git diff --cached --numstat)
lines=$(awk '{s+=$1+$2} END{print s+0}' <<<"$tracked")
files=$(grep -c . <<<"$tracked")
untracked=$(git ls-files --others --exclude-standard)
if [ -n "$untracked" ]; then
  files=$((files + $(wc -l <<<"$untracked")))
  lines=$((lines + $(tr "\n" "\0" <<<"$untracked" | xargs -0 grep -Ihc "" 2>/dev/null | awk "{s+=\$1} END{print s+0}")))
fi

[ "$lines" -lt "$MIN_LINES" ] && [ "$files" -lt "$MIN_FILES" ] && exit 0

reason="Mudança grande não commitada ($files arquivos, ~$lines linhas). Antes de parar: revise com git status/git diff, faça git add dos arquivos relevantes (nunca segredos/.env) e commite. Mensagem: Conventional Commits em português — título <tipo>(escopo): resumo imperativo ≤72 caracteres; linha em branco; corpo curto explicando o porquê e o que mudou (bullets se houver várias partes). SEM linha Co-Authored-By. Se as mudanças forem de assuntos distintos, faça commits separados."
jq -n --arg r "$reason" '{decision:"block", reason:$r}'
