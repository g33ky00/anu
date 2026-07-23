#!/usr/bin/env bash
set -euo pipefail
DEFAULT_CHAT_ID="-5380549950"
CHAT_ID="${TELEGRAM_CHAT_ID:-$DEFAULT_CHAT_ID}"
TOPIC="$1"
if [[ -z "${TOPIC:-}" ]]; then
  echo "CRITICAL: Topic manquant."
  echo "Usage: anu-tg \"<topic>\" [chat_id_override]"
  exit 1
fi
if [[ -n "${2:-}" ]]; then
  CHAT_ID="$2"
fi
export TELEGRAM_CHAT_ID="$CHAT_ID"
aniu="$(command -v anu || true)"
if [[ -z "$aniu" ]]; then
  echo "CRITICAL: binaire anu introuvable dans PATH."
  exit 1
fi
"$aniu" "$TOPIC" --mode 3 --detach
