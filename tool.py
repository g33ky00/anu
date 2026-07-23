#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ANU Mind CLI wrapper — Slash `/anu` triggers this binary.
Orchestration: Python, argparse, calls engine.py via subprocess.

Fixes v1.0.1:
  - DEFAULT_LOG_DIR / _log_line path normalized to single Hermes logs dir
  - removed stale --context references from README/tooling docs
  - DEFAULT_RUN_ROOT / ENGINE_DEFAULT honour HERMES_PROFILE env var
  - _resume() now resumes full pipeline from last completed pass
  - _load_telegram_credentials() token never logged in clear
  - token masked in all _log_line() calls
"""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------------------
# PATHS / PROFILE
# ---------------------------------------------------------------------------
HOME = Path.home()
# PATHS / PROFILE
_PROFILE = os.environ.get("HERMES_PROFILE") or os.environ.get("PROFILE", "dev")
_HERMES_HOME = Path(
    os.environ.get(
        "HERMES_HOME",
        str(Path.home() / ".hermes" / "profiles" / _PROFILE),
    )
)
DEFAULT_RUN_ROOT = _HERMES_HOME / "cron" / "output" / "anu"
DEFAULT_LOG_DIR = _HERMES_HOME / "logs"

# Structural fix (Dette migratoire N4): moteur global invariant quel que soit le profil appelant.
BASE_DIR = Path(os.path.dirname(os.path.realpath(__file__)))
ENGINE_DEFAULT = Path("/home/g33ky/.hermes/skills/autonomous-ai-agents/anu-mind/scripts/engine.py")


def _manifest_update(run_dir: Path, pass_data: dict) -> None:
    mf  = run_dir.resolve() / ".manifest.json"
    tmp = mf.with_suffix(".tmp")
    data: dict = {}
    if mf.exists():
        try:
            data = _read_json(mf)
        except Exception:
            data = {}
    data.setdefault("passes", {}).update(pass_data)
    try:
        tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        os.replace(str(tmp), str(mf))
    except Exception as e:
        _log_line(f"CRITICAL: manifest write failed run_dir={run_dir.name}: {e}")
        raise


MODES = {
    1: "ARCHITECT",
    2: "CODER",
    3: "TEACHER",
    4: "PROTOCOL",
    5: "AUDITOR",
    6: "WRITER",
    7: "RESEARCHER",
}
MODE_KEYWORDS = {
    1: ["architecture", "systeme", "infrastructure", "design", "schema", "stack"],
    2: ["code", "debug", "script", "fonction", "implemente", "refactor", "bug"],
    3: ["explique", "tutoriel", "apprends", "documentation", "guide", "apprendre"],
    4: ["procedure", "spec", "protocole", "workflow", "yaml", "json", "api"],
    5: ["audit", "securite", "risque", "vulnerabilite", "analyse"],
    6: ["redige", "ecris", "article", "rapport", "resume", "synthese"],
    7: ["recherche", "compare", "evalue", "benchmark", "faits"],
}

# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(ZoneInfo("UTC")).isoformat()


def _log_line(msg: str) -> None:
    day      = datetime.now().strftime("%Y-%m-%d")
    log_path = DEFAULT_LOG_DIR / f"hermes_{day}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"[{_now_iso()}] [AUTONOMOUS] [anu_mind] {msg}\n")


# ---------------------------------------------------------------------------
# OUTPUT HELPERS
# ---------------------------------------------------------------------------

def _info(msg: str) -> None:
    print(msg, flush=True)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_md(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _score_from_p2(path: Path) -> tuple[float, dict]:
    data  = _read_json(path)
    score = data.get("score") or {}
    mean  = sum(score.values()) / len(score) if score else 0.0
    return mean, score


def _mask_token(token: str) -> str:
    """Returns sk-****...xxxx pattern, never full token."""
    if len(token) <= 8:
        return "****"
    return f"{token[:4]}****...{token[-4:]}"


# ---------------------------------------------------------------------------
# ENGINE INVOCATION
# ---------------------------------------------------------------------------

def _call_engine(args: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    cmd = [sys.executable, str(ENGINE_DEFAULT)] + args
    _log_line(f"engine cmd=`{' '.join(cmd)}`")
    proc = subprocess.run(
        cmd,
        cwd=str(cwd or HOME),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _engine_pass(
    run_dir: Path,
    pass_id: str,
    topic: str,
    mode: int,
    input_file: Path | None = None,
) -> tuple[Path, dict]:
    args = [
        "--topic", topic,
        "--mode",  str(mode),
        "--pass",  pass_id,
        "--run-id", run_dir.name,
    ]
    if input_file:
        args += ["--input", str(input_file)]
    code, out, err = _call_engine(args, cwd=run_dir)
    if code != 0:
        raise RuntimeError(f"engine.py failed for {pass_id}: {err.strip() or out.strip()}")
    ck = _read_json(run_dir / f"{pass_id}.json")
    return run_dir / f"{pass_id}.md", ck


# ---------------------------------------------------------------------------
# TELEGRAM
# ---------------------------------------------------------------------------

def _load_telegram_credentials() -> tuple[str, str | None]:
    """Returns (bot_token, chat_id). Token is never logged in clear.

    Resolution order (first match wins):
      1) Dynamic context from Gateway: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID
      2) Profile context: HERMES_HOME/profiles/<active>/auth.json
      3) Global fallback: HERMES_HOME/auth.json
      4) Profile config.yaml shallow parse
    """
    missing = []

    def _read_auth(p: Path) -> tuple[str, str | None] | None:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            providers = data.get("providers", {}) if isinstance(data, dict) else {}
            for name in ("telegram", "tg"):
                item = providers.get(name)
                if isinstance(item, dict):
                    tk = item.get("access_token") or item.get("bot_token") or item.get("token")
                    chat = item.get("chat_id") or item.get("admin_chat_id")
                    if tk:
                        return tk, chat
        except Exception:
            pass
        return None

    # 1) Dynamic context from Gateway
    dyn_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    dyn_chat = os.getenv("TELEGRAM_CHAT_ID")
    if dyn_token:
        return dyn_token, dyn_chat
    if not dyn_token:
        missing.append("token")
    if not dyn_chat:
        missing.append("chat_id")

    # 2) Profile auth.json
    profile_auth = _HERMES_HOME / "profiles" / os.environ.get("PROFILE", "dev") / "auth.json"
    if profile_auth.exists():
        got = _read_auth(profile_auth)
        if got:
            return got

    # 3) Global auth.json
    global_auth = Path("/home/g33ky/.hermes/auth.json")
    if global_auth.exists():
        got = _read_auth(global_auth)
        if got:
            return got

    # 4) config.yaml shallow parse
    config_path = _HERMES_HOME / "config.yaml"
    if config_path.exists():
        txt = config_path.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"telegram:\s*\n(?:[^\n]*\n)*?\s*(?:bot_token|token):\s*[\"']?([^\"'\n]+)", txt)
        if m:
            token = m.group(1).strip()
            chat_id = os.getenv("TELEGRAM_CHAT_ID")
            return token, chat_id

    _log_line(f"telegram_push_failed reason=credentials_missing missing={sorted(set(missing))}")
    return "", None


def _telegram_push(text: str, chat_id: str | None = None, run_id: str | None = None) -> bool:
    token, default_chat = _load_telegram_credentials()
    if not token:
        _log_line("telegram_push_failed reason=credentials_missing missing=token")
        return False

    chat = chat_id or default_chat
    if not chat:
        _log_line("telegram_push_failed reason=credentials_missing missing=chat_id")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat,
        "text": text,
        "disable_web_page_preview": True,
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        _log_line("telegram_push_start")
        with urllib.request.urlopen(req, timeout=180) as response:
            ok = response.status == 200
            rid = run_id or "-"
            if ok:
                _log_line(f"telegram_push_success run_id={rid} status=ok target_chat={chat}")
            else:
                _log_line(f"telegram_push_failed http_status={response.status}")
            return ok
    except Exception as e:
        _log_line(f"telegram_push_failed error={e!r}")
        return False


def _split_for_telegram(text: str, limit: int = 4096) -> list[str]:
    parts = []
    while text:
        if len(text) <= limit:
            parts.append(text)
            break
        cut = text.rfind("\n", 0, limit)
        if cut == -1:
            cut = text.rfind(" ", 0, limit)
        if cut == -1:
            cut = limit
        parts.append(text[:cut])
        text = text[cut:].lstrip("\n ")
    return parts


# ---------------------------------------------------------------------------
# DETACH / FORK
# ---------------------------------------------------------------------------

def _exec_detached(run_dir: Path, topic: str, mode: int, *, reply_to: str | None = None, bot_token: str | None = None) -> None:
    script      = str(Path(__file__).resolve())
    uid         = str(os.getuid())
    env         = os.environ.copy()

    if "XDG_RUNTIME_DIR" not in env:
        env["XDG_RUNTIME_DIR"] = f"/run/user/{uid}"
    if "DBUS_SESSION_BUS_ADDRESS" not in env:
        env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path=/run/user/{uid}/bus"
    if "HOME" not in env:
        env["HOME"] = os.path.expanduser("~")
    if "USER" not in env:
        env["USER"] = "g33ky"
    if "PROFILE" not in env:
        env["PROFILE"] = "dev"
    if "HERMES_HOME" not in env:
        env["HERMES_HOME"] = f"/home/g33ky/.hermes/profiles/{env['PROFILE']}"

    chat_for_child = reply_to or env.get('TELEGRAM_CHAT_ID') or env.get('HERMES_SESSION_CHAT_ID', '')
    token_for_child = bot_token or env.get('TELEGRAM_BOT_TOKEN', '')
    cmd = [
        "systemd-run", "--user",
        "--unit",    f"anu-run-{run_dir.name}",
        "--collect",
        f"--setenv=TELEGRAM_CHAT_ID={chat_for_child}",
        f"--setenv=TELEGRAM_BOT_TOKEN={token_for_child}",
        f"--setenv=PROFILE={env['PROFILE']}",
        f"--setenv=HERMES_HOME={env['HERMES_HOME']}",
        f"--setenv=PATH={env.get('PATH', '')}",
        sys.executable, script,
        "--parent",
        "--topic",  topic,
        "--mode",   str(mode),
        "--run-id", run_dir.name,
    ]
    masked_cmd = ' '.join(
        f"--setenv=TELEGRAM_BOT_TOKEN=****{token_for_child[-4:]}" if token_for_child else part
        if part.startswith("--setenv=TELEGRAM_BOT_TOKEN=") else part
        for part in cmd
    )
    _log_line(f"systemd-run cmd=`{masked_cmd}`")
    subprocess.Popen(
        cmd, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
        close_fds=True,
    )


def _run_pipeline_with_callback(run_dir: Path, topic: str, mode: int) -> None:
    run_id = run_dir.name
    try:
        summary = _run_pipeline(run_dir, topic, mode)
    except Exception as exc:
        msg = (
            f"\U0001f6a8 [ANU - ERREUR FATALE] Échec pipeline.\n"
            f"Reprise : /anu --resume {run_id}\nErreur : {exc!r}"
        )
        _telegram_push(msg, run_id=run_id)
        _log_line(f"run_failed run_id={run_id} error={exc!r}")
        return

    p2_mean = (summary.get("p2") or {}).get("mean") or 0.0
    passes_count = sum(
        1 for p in ["p1", "p2", "p3", "p4"]
        if summary.get(p) and summary[p].get("status") != "skipped"
    )
    p4_md = run_dir / "p4.md"
    if not p4_md.exists():
        msg = (
            f"\U0001f6a8 [ANU - ERREUR FATALE] Livrable p4.md manquant.\n"
            f"Reprise : /anu --resume {run_id}"
        )
        _telegram_push(msg)
        _log_line(f"run_failed missing_p4 run_id={run_id}")
        return

    content = _read_md(p4_md)
    header  = f"[ANU | {MODES[mode]} | Run {run_id} | Score P2: {p2_mean:.1f}/10]\n"
    chunks  = _split_for_telegram(header + content)
    for i, chunk in enumerate(chunks):
        sent = _telegram_push(chunk, run_id=run_id)
        _log_line(
            f"telegram_push run_id={run_id} "
            f"part={i+1}/{len(chunks)} status={'ok' if sent else 'failed'}"
        )
    _log_line(
        f"run_completed run_id={run_id} mode={mode} "
        f"score_p2={p2_mean} passes={passes_count}"
    )


# ---------------------------------------------------------------------------
# PIPELINE
# ---------------------------------------------------------------------------

def _detect_mode(topic: str) -> int:
    t = topic.lower()
    # Priorité absolue à l'intention pédagogique : matching par mot
    teacher_keywords = MODE_KEYWORDS.get(3, [])
    if any(re.search(rf"\b{re.escape(k)}\b", t) for k in teacher_keywords):
        return 3
    # Matching substring standard pour les autres modes
    for mid, keywords in MODE_KEYWORDS.items():
        if mid == 3:
            continue
        if any(k in t for k in keywords):
            return mid
    return 2  # CODER fallback


def _run_pipeline(run_dir: Path, topic: str, mode: int) -> dict:
    summary: dict = {"p1": None, "p2": None, "p3": None, "p4": None}

    # P1
    _info(f"[ANU | {MODES[mode]}] P1 génération... ⏳")
    p1_md, p1_ck = _engine_pass(run_dir, "p1", topic, mode)
    summary["p1"] = {"status": p1_ck.get("status"), "file": "p1.md"}
    _manifest_update(run_dir, {"p1": summary["p1"]})
    _info(f"[ANU | {MODES[mode]}] P1 ✅")

    # P2
    _info(f"[ANU | {MODES[mode]}] P2 audit... ⏳")
    p2_md, p2_ck = _engine_pass(run_dir, "p2", topic, mode, input_file=p1_md)
    mean, score  = _score_from_p2(run_dir / "p2.json")
    summary["p2"] = {"status": p2_ck.get("status"), "file": "p2.md", "score": score, "mean": mean}
    _manifest_update(run_dir, {"p2": summary["p2"]})
    _info(f"[ANU | {MODES[mode]}] P2 score: {mean:.1f}/10")

    # P3 conditionnel
    CRITICAL_LOW = 5
    needs_p3 = mean < 7.0 or any(
        (score.get(d) or 10) < CRITICAL_LOW
        for d in ["factualite", "couverture", "coherence", "risques", "clarte"]
    )
    if needs_p3:
        _info(f"[ANU | {MODES[mode]}] P3 correction... ⏳")
        p3_md, p3_ck = _engine_pass(run_dir, "p3", topic, mode, input_file=p2_md)
        summary["p3"] = {"status": p3_ck.get("status"), "file": "p3.md"}
        _manifest_update(run_dir, {"p3": summary["p3"]})
        _info(f"[ANU | {MODES[mode]}] P3 ✅")
        last_input = p3_md
    else:
        _info(f"[ANU | {MODES[mode]}] P3 skipped (score OK)")
        summary["p3"] = {"status": "skipped", "file": None}
        _manifest_update(run_dir, {"p3": summary["p3"]})
        last_input = p2_md

    # P4
    _info(f"[ANU | {MODES[mode]}] P4 validation... ⏳")
    _, p4_ck = _engine_pass(run_dir, "p4", topic, mode, input_file=last_input)
    summary["p4"] = {"status": p4_ck.get("status"), "file": "p4.md"}
    _manifest_update(run_dir, {"p4": summary["p4"]})
    _info(f"[ANU | {MODES[mode]}] P4 ✅")

    return summary


# ---------------------------------------------------------------------------
# COMMANDS
# ---------------------------------------------------------------------------

def _print_help() -> None:
    print(
        "Usage: anu <topic> [--mode N] [--resume RUN_ID] [--status] [--detach]\n\n"
        "Modes:\n"
        + "\n".join(f"  {k}  {v}" for k, v in MODES.items())
        + "\n\nExemples:\n"
        "  anu \"audit SSH\" --mode 5\n"
        "  anu \"refactor parser.py\" --mode 2\n"
        "  anu --status\n"
        "  anu --resume 20260718_143022\n"
        "  anu \"Résumé BGP\" --mode 1 --detach\n"
    )


def _status(run_root: Path) -> None:
    if not run_root.exists() or not any(run_root.iterdir()):
        print("No ANU runs.")
        return
    rows = []
    for rd in sorted(run_root.iterdir(), reverse=True)[:20]:
        mf = rd / ".manifest.json"
        if not mf.exists():
            continue
        try:
            data = _read_json(mf)
        except Exception:
            continue
        passes = data.get("passes", {})
        p4     = passes.get("p4", {})
        p2m    = (passes.get("p2") or {}).get("mean", 0.0)
        rows.append((rd.name, p4.get("status", "incomplete"), p2m))
    if not rows:
        print("No ANU runs.")
        return
    print(f"{'run_id':<22} {'p4_status':<14} {'score_p2'}")
    print("-" * 48)
    for name, status, score in rows:
        print(f"{name:<22} {str(status):<14} {score:.1f}")


def _resume(run_root: Path, run_id: str, topic_hint: str | None = None) -> None:
    """
    Reprend le pipeline complet depuis la première passe non complétée.
    FIX v1.0.1: exécution de toutes les passes manquantes (pas seulement la suivante).
    """
    rd = run_root / run_id
    if not rd.exists():
        print(f"Run not found: {run_id}")
        raise SystemExit(1)

    # Déterminer les passes complétées depuis le manifest
    completed: set[str] = set()
    mf = rd / ".manifest.json"
    if mf.exists():
        try:
            passes = _read_json(mf).get("passes", {})
            completed = {
                p for p, v in passes.items()
                if isinstance(v, dict) and v.get("status") in ("completed", "skipped")
            }
        except Exception:
            pass
    # Fallback sur les .json présents
    if not completed:
        completed = {f.stem for f in rd.glob("*.json") if not f.name.startswith(".")}

    # Récupérer topic + mode depuis le dernier checkpoint disponible
    topic = topic_hint
    mode  = 2
    for p in ["p1", "p2", "p3", "p4"]:
        ck_path = rd / f"{p}.json"
        if ck_path.exists():
            try:
                ck    = _read_json(ck_path)
                topic = topic or ck.get("topic")
                mode  = int(ck.get("mode_id") or 2)
            except Exception:
                pass

    if not topic:
        topic = input("Topic > ").strip()
    if not topic:
        raise SystemExit("Missing topic.")

    if {"p1", "p2", "p4"} <= completed:
        print(f"Run {run_id} already complete (P4 done).")
        return

    print(f"[ANU] Reprise run={run_id} complétées={sorted(completed)} mode={mode}")
    _log_line(f"run_resume run_id={run_id} completed={sorted(completed)} mode={mode}")

    # Relancer depuis la première passe non complétée
    # On reconstruit le pipeline en passant les passes déjà faites
    p1_md = rd / "p1.md"
    p2_md = rd / "p2.md"
    p3_md = rd / "p3.md"

    if "p1" not in completed:
        _info(f"[ANU | {MODES[mode]}] P1 génération... ⏳")
        p1_md, p1_ck = _engine_pass(rd, "p1", topic, mode)
        _manifest_update(rd, {"p1": {"status": p1_ck.get("status"), "file": "p1.md"}})
        _info(f"[ANU | {MODES[mode]}] P1 ✅")

    if "p2" not in completed:
        _info(f"[ANU | {MODES[mode]}] P2 audit... ⏳")
        p2_md, p2_ck = _engine_pass(rd, "p2", topic, mode, input_file=p1_md)
        mean, score  = _score_from_p2(rd / "p2.json")
        _manifest_update(rd, {"p2": {"status": p2_ck.get("status"), "file": "p2.md", "score": score, "mean": mean}})
        _info(f"[ANU | {MODES[mode]}] P2 score: {mean:.1f}/10")
    else:
        mean, score = _score_from_p2(rd / "p2.json") if (rd / "p2.json").exists() else (0.0, {})

    needs_p3 = mean < 7.0 or any((score.get(d) or 10) < 5 for d in ["factualite", "couverture", "coherence", "risques", "clarte"])
    if needs_p3 and "p3" not in completed:
        _info(f"[ANU | {MODES[mode]}] P3 correction... ⏳")
        p3_md, p3_ck = _engine_pass(rd, "p3", topic, mode, input_file=p2_md)
        _manifest_update(rd, {"p3": {"status": p3_ck.get("status"), "file": "p3.md"}})
        _info(f"[ANU | {MODES[mode]}] P3 ✅")
        last_input = p3_md
    elif not needs_p3:
        _manifest_update(rd, {"p3": {"status": "skipped", "file": None}})
        last_input = p2_md
    else:
        last_input = p3_md if p3_md.exists() else p2_md

    if "p4" not in completed:
        _info(f"[ANU | {MODES[mode]}] P4 validation... ⏳")
        _, p4_ck = _engine_pass(rd, "p4", topic, mode, input_file=last_input)
        _manifest_update(rd, {"p4": {"status": p4_ck.get("status"), "file": "p4.md"}})
        _info(f"[ANU | {MODES[mode]}] P4 ✅")

    p4_md_path = rd / "p4.md"
    if p4_md_path.exists():
        _info("\n" + "=" * 40 + "\n[ANU] LIVRAISON (resumé)\n" + "=" * 40)
        print(_read_md(p4_md_path))
    _log_line(f"run_resume_completed run_id={run_id} mode={mode}")


# ---------------------------------------------------------------------------
# MAIN / DISPATCHER
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(prog="anu", add_help=False)
    parser.add_argument("topic", nargs="?", default=None)
    parser.add_argument("--mode",   type=int, default=None)
    parser.add_argument("--resume", default=None)
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--detach", "-d", action="store_true")
    parser.add_argument("--help",   action="store_true")
    args = parser.parse_args()

    if args.help or (not args.topic and not args.resume and not args.status):
        _print_help()
        return 0

    if args.status:
        _status(DEFAULT_RUN_ROOT)
        return 0

    if args.resume:
        _resume(DEFAULT_RUN_ROOT, args.resume, topic_hint=args.topic)
        return 0

    topic = (args.topic or "").strip()
    if not topic:
        print("Missing topic.")
        _print_help()
        return 2

    mode = args.mode if args.mode is not None else _detect_mode(topic)
    if mode not in MODES:
        print(f"Invalid mode: {mode}. Allowed: {sorted(MODES)}")
        return 2

    run_id  = datetime.now().strftime("%Y%m%d_%H%M%S")
    current_profile = os.environ.get("PROFILE", "dev")
    base_profile_dir = os.environ.get(
        "HERMES_HOME",
        f"/home/g33ky/.hermes/profiles/{current_profile}",
    )
    run_dir = Path(os.path.join(base_profile_dir, "cron", "output", "anu", run_id))
    run_dir.mkdir(parents=True, exist_ok=False)

    if args.detach:
        print(f"[ANU] Run {run_id} détaché (mode: {MODES[mode]}) — callback Telegram à la fin")
        _log_line(f"run_start_detach run_id={run_id} mode={mode}")
        _exec_detached(run_dir, topic, mode)
        return 0

    print(f"[ANU] Démarrage mode {mode} ({MODES[mode]}) — run_id: {run_id}")
    _log_line(f"run_start run_id={run_id} mode={mode} topic={topic[:80]!r}")
    try:
        summary = _run_pipeline(run_dir, topic, mode)
    except Exception as exc:
        _log_line(f"run_failed run_id={run_id} error={exc!r}")
        print(f"[ANU] FAILED: {exc}")
        return 1

    p2_mean     = (summary.get("p2") or {}).get("mean") or 0.0
    passes_done = sum(
        1 for p in ["p1", "p2", "p3", "p4"]
        if summary.get(p) and summary[p].get("status") != "skipped"
    )
    p4_md = run_dir / "p4.md"
    if p4_md.exists():
        _info("\n" + "=" * 40 + "\n[ANU] LIVRAISON\n" + "=" * 40)
        print(_read_md(p4_md))
        _info("=" * 40)
        _info(f"[ANU] run_id={run_id} | mode={MODES[mode]} | score_p2={p2_mean:.1f}/10 | passes={passes_done}")
    else:
        print("[ANU] Terminé sans livrable p4.md.")

    _log_line(f"run_completed run_id={run_id} mode={mode} score_p2={p2_mean} passes={passes_done}")
    return 0


# ---------------------------------------------------------------------------
# CHILD ENTRY POINT (--parent flag — invoked by systemd-run detach)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if "--parent" in sys.argv:
        sys.argv.remove("--parent")
        p = argparse.ArgumentParser(prog="anu-child", add_help=False)
        p.add_argument("--topic",  required=True)
        p.add_argument("--mode",   required=True, type=int)
        p.add_argument("--run-id", required=True)
        a = p.parse_args()
        if a.mode not in MODES:
            print(f"Invalid mode: {a.mode}")
            raise SystemExit(2)

        current_profile = os.environ.get("PROFILE", "dev")
        base_profile_dir = os.environ.get(
            "HERMES_HOME",
            f"/home/g33ky/.hermes/profiles/{current_profile}",
        )
        child_run_dir = Path(os.path.join(base_profile_dir, "cron", "output", "anu", a.run_id))
        if not child_run_dir.exists():
            raise SystemExit(f"Missing run_dir: {child_run_dir}")

        _run_pipeline_with_callback(child_run_dir, a.topic, a.mode)
        raise SystemExit(0)

    raise SystemExit(main())
