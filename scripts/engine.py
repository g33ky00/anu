#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ANU Mind Engine — orchestrateur 4 passes (P1→P2→P3→P4).
Déterministe, non interactif, backend LLM injecté via Hermes config.
"""

import os
import sys
import json
import re
import time
import argparse
import hashlib
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# CHEMINS / NOMENCLATURE
# ---------------------------------------------------------------------------
RUN_ROOT = Path.home() / ".hermes" / "profiles" / "dev" / "cron" / "output" / "anu"
TIME_FMT = "%Y%m%d_%H%M%S"

# ---------------------------------------------------------------------------
# MODES ARCHÉTYPES
# ---------------------------------------------------------------------------
MODES = {
    1: {"name": "ARCHITECT",   "temperature": 0.7, "max_tokens": 8192},
    2: {"name": "CODER",       "temperature": 0.2, "max_tokens": 8192},
    3: {"name": "TEACHER",     "temperature": 0.6, "max_tokens": 8192},
    4: {"name": "PROTOCOL",    "temperature": 0.0, "max_tokens": 4096},
    5: {"name": "AUDITOR",     "temperature": 0.3, "max_tokens": 4096},
    6: {"name": "WRITER",      "temperature": 0.8, "max_tokens": 8192},
    7: {"name": "RESEARCHER",  "temperature": 0.2, "max_tokens": 8192},
}

SYSTEM_PROMPTS = {
    1: "ROLE: System Architect. OUTPUT: Mermaid.js + Functional Blocks. CONTEXT: Scalability. LANG: French.",
    2: "ROLE: Senior Dev. OUTPUT: Pure Code + Comments. STYLE: Production Ready. LANG: Code/French.",
    3: "ROLE: Expert Pedagogue. OUTPUT: Tutorial + Analogies. TARGET: Junior. LANG: French.",
    4: "ROLE: API/Machine. OUTPUT: Strict JSON/YAML. CONSTRAINT: No chatter, raw data. LANG: English.",
    5: "ROLE: SecOps. TASK: Threat Modeling. OUTPUT: Risk Table. MINDSET: Paranoid/OWASP. LANG: French.",
    6: "ROLE: Copywriter. OUTPUT: Blog Post. STYLE: SEO-friendly, H2/H3. LANG: French.",
    7: "ROLE: Web Researcher. TASK: Scour web. OUTPUT: List + Sources + Date. CONSTRAINT: Use provided context as verified premise. If fact is not verifiable, state 'UNVERIFIED'. Never invent facts. LANG: French.",
}

# ---------------------------------------------------------------------------
# WORKFLOW CONSTRAINTS
# ---------------------------------------------------------------------------
ALLOWED_TRANSITIONS = {
    "p1": ["p2"],
    "p2": ["p3", "p4"],
    "p3": ["p4"],
    "p4": [],
}

AUDIT_THRESHOLD_TOTAL = 7        # moyenne /10 pour valider P2 sans correction
AUDIT_THRESHOLD_CRITICAL = 5     # seuil dimension critique
MAX_CORRECTION_PASSES = 3        # plafond P2→P3 pour éviter boucle infinie
DIMENSIONS = ["factualite", "couverture", "coherence", "risques", "clarte"]

# Regex masking secrets dans les sorties
_SECRET_RE = re.compile(
    r"(?i)(sk-[a-zA-Z0-9]{20,}|api[_-]?key\s*[:=]\s*[^\s]+|token\s*[:=]\s*[^\s]+|bearer\s+[^\s]+)"
)

# ---------------------------------------------------------------------------
# UTILITAIRES
# ---------------------------------------------------------------------------
def prompt_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def scrub_secrets(text: str) -> str:
    return _SECRET_RE.sub(lambda m: m.group(0)[:4] + "****", text)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def utc_now_ts() -> str:
    return datetime.now(timezone.utc).strftime(TIME_FMT)


def log_autonomous(run_id: str, pass_id: str, mode: int, topic: str, status: str, tokens: int = 0):
    log_file = Path.home() / ".hermes" / "profiles" / "dev" / "logs" / f"hermes_{datetime.now().strftime('%Y-%m-%d')}.log"
    entry = (
        f"[{utc_now_iso()}] [AUTONOMOUS] [anu_mind] [{pass_id.upper()}] "
        f"run_id={run_id} mode={mode} topic_hash={prompt_hash(topic)} status={status} tokens={tokens}\n"
    )
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as f:
        f.write(entry)


def write_checkpoint_atomic(run_dir: Path, ck: dict) -> Path:
    path = run_dir / f"{ck['pass_id']}.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(ck, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def make_run_dir(run_id: Optional[str] = None) -> Path:
    rid = run_id or utc_now_ts()
    run_dir = RUN_ROOT / rid
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


# ---------------------------------------------------------------------------
# SCORING P2 (dimensions 0-10)
# ---------------------------------------------------------------------------
def compute_score(audit_md: str) -> Dict[str, int]:
    scores: Dict[str, int] = {}
    for dim in DIMENSIONS:
        m = re.search(rf"(?i)\|\s*{re.escape(dim)}\s*\|\s*(\d+)\s*\|", audit_md)
        scores[dim] = int(m.group(1)) if m else 0
    return scores


# ---------------------------------------------------------------------------
# AUTH / CONFIG PROVIDER (Stepfun/Nous via Hermes config)
# ---------------------------------------------------------------------------
_CONFIG_CACHE: Dict[str, Any] = {}
_AUTH_CACHE: Dict[str, Any] = {}


def _load_config() -> Dict[str, Any]:
    global _CONFIG_CACHE
    if _CONFIG_CACHE:
        return _CONFIG_CACHE
    cfg_path = Path.home() / ".hermes" / "config.yaml"
    text = cfg_path.read_text(encoding="utf-8") if cfg_path.exists() else ""
    _CONFIG_CACHE = {
        "provider": "",
        "default_model": "",
        "base_url": "",
        "api_key": "",
    }
    in_model_block = False
    for raw_line in text.splitlines():
        line = raw_line.rstrip("\n")
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == "model:":
            in_model_block = True
            continue
        if in_model_block and stripped and not stripped.startswith(" ") and not stripped.startswith("-") and ":" in stripped:
            in_model_block = False
            continue
        if in_model_block and stripped and not stripped.startswith("-") and ":" in stripped:
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key in ("provider", "default", "base_url", "api_key"):
                if key == "provider":
                    _CONFIG_CACHE["provider"] = val
                elif key == "default":
                    _CONFIG_CACHE["default_model"] = val
                elif key == "base_url":
                    _CONFIG_CACHE["base_url"] = val
                elif key == "api_key":
                    _CONFIG_CACHE["api_key"] = val
    return _CONFIG_CACHE


def _load_auth() -> Dict[str, Any]:
    global _AUTH_CACHE
    if _AUTH_CACHE:
        return _AUTH_CACHE
    auth_path = Path.home() / ".hermes" / "auth.json"
    try:
        obj = json.loads(auth_path.read_text(encoding="utf-8")) if auth_path.exists() else {}
    except Exception:
        obj = {}
    providers = obj.get("providers") or {}
    active = obj.get("active_provider") or ""
    data = providers.get(active) or providers.get("nous") or {}
    _AUTH_CACHE = {
        "active_provider": active,
        "access_token": data.get("access_token") or "",
        "refresh_token": data.get("refresh_token") or "",
        "client_id": data.get("client_id") or "",
        "token_type": data.get("token_type") or "Bearer",
        "portal_base_url": data.get("portal_base_url") or "https://portal.nousresearch.com",
        "inference_base_url": data.get("inference_base_url") or "https://inference-api.nousresearch.com/v1",
        "agent_key": data.get("agent_key") or "",
        "agent_key_expires_at": data.get("agent_key_expires_at") or "",
        "obtained_at": data.get("obtained_at") or "",
        "expires_at": data.get("expires_at") or "",
    }
    return _AUTH_CACHE


def _mask_token(value: Optional[str]) -> str:
    if isinstance(value, str) and len(value) >= 8:
        return value[:4] + "****" + value[-4:]
    return "<absent>" if not value else "<set>"


def _http_json(url: str, payload: Dict[str, Any], headers: Dict[str, str], timeout: int = 60) -> Dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        text = ""
        try:
            text = e.read().decode("utf-8", errors="replace")
        except Exception:
            text = str(e)
        return {"__http_error__": True, "status": e.code, "reason": str(e), "body": text}


# ---------------------------------------------------------------------------
# LLM BACKEND - Stepfun/Nous compatible OpenAI, reuse Hermes auth
# ---------------------------------------------------------------------------
def _resolved_model(model: str) -> str:
    if model and model != "auto":
        return model
    cfg = _load_config()
    raw = cfg.get("default_model") or "stepfun/step-3.7-flash:free"
    return raw.strip().strip('"').strip("'") or "stepfun/step-3.7-flash:free"


def _resolved_base_url() -> str:
    cfg = _load_config()
    base = cfg.get("base_url") or ""
    if base:
        return base.rstrip("/") + "/chat/completions"
    auth = _load_auth()
    return (auth.get("inference_base_url") or "https://inference-api.nousresearch.com/v1").rstrip("/") + "/chat/completions"


def _refresh_access_token() -> Dict[str, Any]:
    auth = _load_auth()
    refresh_token = auth.get("refresh_token")
    client_id = auth.get("client_id") or "hermes-cli"
    portal_base = (auth.get("portal_base_url") or "https://portal.nousresearch.com").rstrip("/")
    token_url = f"{portal_base}/oauth2/token"
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    form = "&".join(f"{k}={urllib.parse.quote(v)}" for k, v in payload.items())
    req = urllib.request.Request(token_url, data=form.encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            obj = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"ok": False, "error": f"refresh_failed: {type(e).__name__}: {str(e)[:200]}"}

    access_token = obj.get("access_token")
    expires_in = obj.get("expires_in")
    token_type = obj.get("token_type") or "Bearer"
    if not access_token:
        return {"ok": False, "error": "refresh_missing_access_token"}
    try:
        from datetime import timedelta
        expires_at = (datetime.now(timezone.utc) + timedelta(seconds=int(expires_in or 0))).isoformat()
    except Exception:
        expires_at = ""
    return {
        "ok": True,
        "access_token": access_token,
        "token_type": token_type,
        "expires_at": expires_at,
        "refresh_token": obj.get("refresh_token") or refresh_token,
        "scope": obj.get("scope") or auth.get("scope") or "inference:invoke",
        "client_id": client_id,
        "portal_base_url": portal_base,
        "inference_base_url": auth.get("inference_base_url"),
    }


def _llm_backend(model: str, user_prompt: str, system_instruction: str, max_tokens: int, temperature: float) -> str:
    auth = _load_auth()
    access_token = auth.get("access_token") or ""
    base_url = _resolved_base_url()
    target_model = _resolved_model(model)

    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": user_prompt})

    payload = {
        "model": target_model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    def _call(token_value: str) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {token_value}",
            "Content-Type": "application/json",
        }
        return _http_json(base_url, payload, headers)

    if not access_token or auth.get("expires_at", "") < datetime.now(timezone.utc).isoformat():
        refreshed = _refresh_access_token()
        if refreshed.get("ok"):
            access_token = refreshed.get("access_token") or ""
        else:
            return f"[LLM ERROR] Auth refresh failed: {refreshed.get('error')}"

    result = _call(access_token)
    if result.get("__http_error__"):
        status = result.get("status")
        if status in (401, 403):
            refreshed = _refresh_access_token()
            if refreshed.get("ok") and refreshed.get("access_token"):
                result = _call(refreshed["access_token"])
        if result.get("__http_error__"):
            status = result.get("status")
            if status in (401, 403):
                return f"[LLM ERROR] Auth invalid after refresh: HTTP {status}: {result.get('body','')[:200]}"
            return f"[LLM ERROR] HTTP {status}: {result.get('reason','')} {result.get('body','')[:200]}"

    choices = result.get("choices") or []
    text = ""
    if choices:
        msg = choices[0].get("message") or {}
        text = (
            msg.get("content")
            or msg.get("reasoning")
            or ""
        )
        if not text:
            details = msg.get("reasoning_details") or []
            for part in details:
                if isinstance(part, dict) and part.get("type") == "reasoning.text":
                    text = part.get("text") or ""
                    if text:
                        break
    return scrub_secrets(text)


def llm_generate(
    model: str,
    user_prompt: str,
    system_instruction: str,
    max_tokens: int,
    temperature: float,
) -> str:
    return _llm_backend(model, user_prompt, system_instruction, max_tokens, temperature)


# ---------------------------------------------------------------------------
# WORKFLOW PRINCIPAL
# ---------------------------------------------------------------------------
def run_passes(run_dir: Path, args: argparse.Namespace) -> Dict[str, Any]:
    topic: str = args.topic
    mode_id: int = int(args.mode)
    start_pass: str = args.pass_id
    input_path: Optional[Path] = args.input

    result: Dict[str, Any] = {
        "status": "pending",
        "last_pass": None,
        "output_file": None,
        "errors": [],
        "metrics": {},
    }

    if mode_id not in MODES:
        raise ValueError(f"mode_id {mode_id} inconnu. Choix: {sorted(MODES)}")

    if start_pass not in ALLOWED_TRANSITIONS and start_pass != "p1":
        raise ValueError(f"Passe invalide {start_pass}. Valides: p1..p4.")

    if start_pass != "p1":
        idx = ["p1", "p2", "p3", "p4"].index(start_pass)
        for prev in ["p1", "p2", "p3", "p4"][:idx]:
            if not (run_dir / f"{prev}.json").exists():
                raise FileNotFoundError(
                    f"Checkpoint manquant pour la passe source {prev}. Lancer d'abord {prev}."
                )

    target_pass = start_pass
    if target_pass == "p4":
        ck_p2_path = run_dir / "p2.json"
        if ck_p2_path.exists():
            ck_p2 = json.loads(ck_p2_path.read_text(encoding="utf-8"))
            score = ck_p2.get("score") or {}
            mean = sum(score.values()) / len(score) if score else 0
            critical_low = any(score.get(d, 10) < AUDIT_THRESHOLD_CRITICAL for d in DIMENSIONS)
            if mean >= AUDIT_THRESHOLD_TOTAL and not critical_low:
                pass
            else:
                target_pass = "p3"
        else:
            target_pass = "p3"

    correction_attempts = 0
    previous_prompt_hash: Optional[str] = None
    last_pass: Optional[str] = None

    while True:
        mode = MODES[mode_id]
        ck: Dict[str, Any] = {
            "$schema": "checkpoint_v1",
            "run_id": run_dir.name,
            "pass_id": target_pass,
            "mode_id": mode_id,
            "topic": topic,
            "input_file": None,
            "output_file": f"{target_pass}.md",
            "metrics": {"tokens_in": 0, "tokens_out": 0, "wall_time_s": 0.0},
            "status": "running",
            "score": None,
            "errors": [],
        }

        effective_input = None
        if target_pass in ("p2", "p3", "p4"):
            candidate = input_path or (run_dir / f"{['p1','p2','p3'][['p2','p3','p4'].index(target_pass)]}.md")
            if candidate and candidate.exists():
                effective_input = candidate.resolve()
                ck["input_file"] = str(effective_input.relative_to(run_dir))

        user_prompt = effective_input.read_text(encoding="utf-8") if effective_input else topic

        t0 = time.perf_counter()
        raw = llm_generate(
            model="auto",
            user_prompt=user_prompt,
            system_instruction=SYSTEM_PROMPTS[mode_id],
            max_tokens=mode["max_tokens"],
            temperature=mode["temperature"],
        )
        text = scrub_secrets(raw)

        out_md = run_dir / f"{target_pass}.md"
        out_md.write_text(text, encoding="utf-8")

        prompt_tokens = len(user_prompt.split()) + len(SYSTEM_PROMPTS[mode_id].split())
        candidate_tokens = len(text.split())
        ck["metrics"]["tokens_in"] = prompt_tokens
        ck["metrics"]["tokens_out"] = candidate_tokens
        ck["metrics"]["wall_time_s"] = round(time.perf_counter() - t0, 3)

        if target_pass == "p2":
            score = compute_score(text)
            ck["score"] = score
            mean = sum(score.values()) / len(score) if score else 0
            critical_low = any(score.get(d, 10) < AUDIT_THRESHOLD_CRITICAL for d in DIMENSIONS)

            if mean >= AUDIT_THRESHOLD_TOTAL and not critical_low:
                ck["status"] = "completed"
                last_pass = "p2"
            else:
                current_hash = prompt_hash(text)
                if current_hash == previous_prompt_hash:
                    ck["status"] = "failed"
                    ck["errors"].append({"kind": "no_progress", "detail": "identical content after correction"})
                    last_pass = "p2"
                else:
                    ck["status"] = "needs_correction"
                    previous_prompt_hash = current_hash
                    last_pass = "p2"
        else:
            ck["status"] = "completed"
            last_pass = target_pass

        write_checkpoint_atomic(run_dir, ck)
        result["status"] = ck["status"]
        result["last_pass"] = target_pass
        result["output_file"] = ck["output_file"]
        result["errors"] = list(ck.get("errors") or [])
        result["metrics"] = dict(ck.get("metrics") or {})
        log_autonomous(run_dir.name, target_pass, mode_id, topic, ck["status"], ck["metrics"]["tokens_out"])

        if target_pass == "p2" and ck["status"] == "needs_correction":
            if correction_attempts >= MAX_CORRECTION_PASSES:
                ck_final = {**ck, "status": "failed"}
                ck_final["errors"].append({"kind": "max_corrections", "detail": str(MAX_CORRECTION_PASSES)})
                write_checkpoint_atomic(run_dir, ck_final)
                log_autonomous(run_dir.name, ck["pass_id"], mode_id, topic, "failed", ck["metrics"]["tokens_out"])
                break
            correction_attempts += 1
            input_path = out_md
            target_pass = "p3"
            continue

        if target_pass == "p3":
            input_path = out_md
            target_pass = "p4"
            continue

        break

    manifest: Dict[str, Any] = {"run_id": run_dir.name, "passes": {}}
    for p in ["p1", "p2", "p3", "p4"]:
        pj = run_dir / f"{p}.json"
        if pj.exists():
            manifest["passes"][p] = json.loads(pj.read_text(encoding="utf-8"))
    manifest_path = run_dir / ".manifest.json"
    result["status"] = result.get("status") or "completed"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="ANU Mind Engine")
    parser.add_argument("--topic", required=True, help="Sujet brut ANU")
    parser.add_argument("--mode", type=int, required=True, help=f"Archétype {sorted(MODES)}")
    parser.add_argument("--pass", dest="pass_id", required=True, choices=["p1", "p2", "p3", "p4"])
    parser.add_argument("--run-id", required=True, help="Répertoire de run existant YYYYMMDD_HHMMSS")
    parser.add_argument("--input", default=None, help="Chemin markdown d'entrée (p2/p3/p4)")
    args = parser.parse_args()

    run_dir = RUN_ROOT / args.run_id
    if not run_dir.exists():
        raise SystemExit(f"Run introuvable: {run_dir}")

    if args.input:
        args.input = Path(args.input).resolve()
        if not args.input.exists():
            raise SystemExit(f"Input introuvable: {args.input}")
    else:
        args.input = None

    manifest = run_passes(run_dir, args)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
