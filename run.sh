#!/usr/bin/env bash
# loopkit döngü sürücüsü: her turda taze bağlam, durum diskte.
#
# Windows'ta Git Bash ile çalıştır:  bash run.sh
#
# CLI seçimi:
#   LOOPKIT_CLI   son argümanı prompt olan komut. Varsayılan "claude -p".
#                 Diğer ajanlar için: LOOPKIT_CLI="codex exec" / "gemini -p"
#
# Model yönlendirme (yalnız Claude; LOOPKIT_CLI ayarlıysa yok sayılır):
#   CLAUDE_EXECUTOR_MODEL  "sonraki adımı yap" çağrısının --model'i
#   CLAUDE_JUDGE_MODEL     "/verify" çağrısının --model'i
# Bkz. .claude/skills/model-routing/SKILL.md
#
# Ön koşul: proje kökünde PROMPT.md ve IMPLEMENTATION_PLAN.md olmalı (/spec ile üret).
set -euo pipefail

if [ ! -f IMPLEMENTATION_PLAN.md ]; then
  echo "IMPLEMENTATION_PLAN.md yok. Önce /spec çalıştır (veya: echo 'STATUS: not-started' > IMPLEMENTATION_PLAN.md)." >&2
  exit 1
fi

EXEC_ARGS=()
JUDGE_ARGS=()
if [ -z "${LOOPKIT_CLI:-}" ]; then
  [ -n "${CLAUDE_EXECUTOR_MODEL:-}" ] && EXEC_ARGS+=(--model "$CLAUDE_EXECUTOR_MODEL")
  [ -n "${CLAUDE_JUDGE_MODEL:-}" ] && JUDGE_ARGS+=(--model "$CLAUDE_JUDGE_MODEL")
fi

CLI="${LOOPKIT_CLI:-claude -p}"

while true; do
  $CLI "${EXEC_ARGS[@]}" "PROMPT.md ve IMPLEMENTATION_PLAN.md'yi oku. Sonraki adımı yap. Yeşilde commit'le."
  $CLI "${JUDGE_ARGS[@]}" "/verify" || echo "verify başarısız, tekrar denenecek"
  grep -q "^STATUS: done$" IMPLEMENTATION_PLAN.md && { echo "tamamlandı"; break; }
  sleep 5
done
