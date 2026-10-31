#!/usr/bin/env bash
# Stop hook: se código mudou sem mudança em tests/, pede ao Claude que escreva os testes.
input=$(cat)
[ -n "${AUTO_COMMIT_NESTED:-}" ] && exit 0
[ "$(jq -r '.stop_hook_active // false' <<<"$input")" = "true" ] && exit 0
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

changed=$( { git diff HEAD --name-only; git ls-files --others --exclude-standard; } | sort -u)
code=$(grep -E '\.(py|sql|sh)$' <<<"$changed" | grep -vE '^(tests/|\.claude/)')
[ -z "$code" ] && exit 0
grep -q '^tests/' <<<"$changed" && exit 0

reason="Código mudou sem teste novo em tests/: $(tr '\n' ' ' <<<"$code"). Antes de parar: escreva ou atualize testes pytest em tests/ cobrindo essas mudanças (sem rede; use fixtures pequenas), rode make test e corrija falhas. Se a mudança realmente não pede teste, diga por quê."
jq -n --arg r "$reason" '{decision:"block", reason:$r}'
