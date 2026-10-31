#!/usr/bin/env bash
# Stop hook: se houver mudança grande não commitada, pede ao Claude que commite.
input=$(cat)
[ -n "${AUTO_COMMIT_NESTED:-}" ] && exit 0
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

reason="Mudança grande não commitada ($files arquivos, ~$lines linhas). Antes de parar: revise com git status, faça git add dos arquivos relevantes (nunca segredos/.env) e rode \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/ai-commit.sh — ele gera a mensagem com Sonnet 5.5 (effort low) e commita. Não escreva a mensagem você mesmo. Se houver assuntos distintos, faça add + ai-commit.sh separadamente para cada um."
jq -n --arg r "$reason" '{decision:"block", reason:$r}'
