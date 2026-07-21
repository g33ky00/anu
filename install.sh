#!/usr/bin/env bash
set -euo pipefail
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$HOME/.local/bin"
ln -snf "$REPO_DIR/install/anu-tg.sh" "$HOME/.local/bin/anu-tg"
chmod +x "$REPO_DIR/install/anu-tg.sh" "$HOME/.local/bin/anu-tg"
