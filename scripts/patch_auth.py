#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_auth.py — Injection sécurisée du provider Telegram dans /home/g33ky/.hermes/auth.json
Usage:
  python3 patch_auth.py <BOT_TOKEN> <CHAT_ID>
Préconditions:
  - auth.json existe
  - Les secrets ne sont jamais affichés en clair en sortie
"""
import json
import sys
from pathlib import Path

AUTH_PATH = Path("/home/g33ky/.hermes/auth.json")


def validate_args():
    if len(sys.argv) != 3:
        print("Usage: python3 patch_auth.py <BOT_TOKEN> <CHAT_ID>")
        sys.exit(2)
    token = sys.argv[1].strip()
    chat_id = sys.argv[2].strip()
    if not token or not chat_id:
        print("ERROR: BOT_TOKEN and CHAT_ID must be non-empty")
        sys.exit(2)
    return token, chat_id


def main():
    token, chat_id = validate_args()
    try:
        data = json.loads(AUTH_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"ERROR: cannot read auth.json: {e}")
        sys.exit(1)

    providers = data.setdefault("providers", {})
    telegram = providers.setdefault("telegram", {})
    telegram["bot_token"] = token
    telegram["chat_id"] = chat_id

    tmp = AUTH_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(AUTH_PATH)
    print("OK telegram provider injected into auth.json")
    print(f"  path={AUTH_PATH}")
    print(f"  token={token[:4]}****...{token[-4:]}")
    print(f"  chat_id={chat_id}")


if __name__ == "__main__":
    main()
