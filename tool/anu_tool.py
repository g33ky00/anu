#!/usr/bin/env python3
"""
/anu — Custom Hermes tool.
Point d'entrée unique du pipeline ANU Mind.

Usage (via Hermes slash command):
  /anu <topic>              # mode auto-détecté
  /anu <topic> --mode N     # force archétype 1-7
  /anu --resume <run_id>    # reprise depuis dernier checkpoint
  /anu --status             # liste runs récents
  /anu                      # aide

Ne jamais appeler engine.py directement — passer exclusivement par ce tool.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import Optional

# ── Chemins canoniques ────────────────────────────────────────────────────────
TOOL_DIR   = Path(__file__).resolve().parent
SKILL_DIR  = TOOL_DIR.parent
ENGINE_PY  = SKILL_DIR / "scripts" / "engine.py"

# Résolution du profile actif (THAECREATIONS_PROFILE ou dev par défaut)
import os
_PROFILE = os.environ.get("THAECREATIONS_PROFILE") or os.environ.get("HERMES_PROFILE", "dev")
_HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
OUTPUT_BASE = _HERMES_HOME / "profiles" / _PROFILE / "cron" / "output" / "anu"
LOG_DIR     = _HERMES_HOME / "profiles" / _PROFILE / "logs"

# ── Mapping auto archétype ────────────────────────────────────────────────────
MODE_KEYWORDS: dict[int, list[str]] = {
    1: ["architecture", "système", "infrastructure", "design", "schéma", "diagram"],
    2: ["code", "debug", "script", "fonction", "implémente", "refactor", "bug"],
    3: ["explique", "tutoriel", "apprends", "documentation", "guide", "pédagogie"],
    4: ["procédure", "spec", "protocole", "workflow", "yaml", "json", "format"],
    5: ["audit", "sécurité", "risque", "vulnérabilité", "analyse", "pentest"],
    6: ["rédige", "écris", "article", "rapport", "résumé", "synthèse", "rédaction"],
    7: ["recherche", "compare", "évalue", "benchmark", "faits", "étude"],
}
MODE_NAMES = {
    1: "ARCHITECT", 2: "CODER", 3: "TEACHER",
    4: "PROTOCOL", 5: "AUDITOR", 6: "WRITER", 7: "RESEARCHER",
}
DEFAULT_MODE = 2  # CODER fallback


# ── Logger minimal ────────────────────────────────────────────────────────────
def _log_autonomous(msg: str) -> None:
    """Écrit dans hermes_YYYY-MM-DD.log au niveau AUTONOMOUS."""
    # TODO: Hermes — utiliser get_logger("anu_tool") si disponible dans le contexte
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / f"hermes_{datetime.now().strftime('%Y-%m-%d')}.log"
    entry = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [AUTONOMOUS] [tool:/anu] {msg}\n"
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(entry)
    except OSError:
        pass


def _print(msg: str) -> None:
    print(msg, flush=True)


# ── Détection automatique du mode ─────────────────────────────────────────────
def detect_mode(topic: str) -> int:
    """
    Analyse topic et retourne le mode_id le plus adapté.
    Retourne DEFAULT_MODE si aucun match.
    """
    # TODO: Hermes — améliorer avec scoring pondéré si pertinent
    topic_lower = topic.lower()
    for mode_id, keywords in MODE_KEYWORDS.items():
        if any(kw in topic_lower for kw in keywords):
            return mode_id
    return DEFAULT_MODE


# ── Validation prérequis ──────────────────────────────────────────────────────
def check_prerequisites() -> list[str]:
    """
    Vérifie que l'environnement est prêt.
    Retourne une liste d'erreurs (vide = OK).
    """
    errors = []
    if not ENGINE_PY.exists():
        errors.append(f"engine.py introuvable : {ENGINE_PY}")
    # TODO: Hermes — ajouter smoke test llm_generate() si possible
    return errors


# ── Chargement engine ─────────────────────────────────────────────────────────
def _load_engine():
    """
    Charge engine.py via importlib.
    Retourne le module engine.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location("anu_engine", ENGINE_PY)
    engine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    return engine


# ── Exécution pipeline ────────────────────────────────────────────────────────
def run_pipeline(
    topic: str,
    mode_id: int,
    run_id: str,
    start_pass: str = "p1",
) -> dict:
    """
    Orchestre les 4 passes ANU via engine.run_passes().
    Gère la logique P3 conditionnel selon score P2.
    Retourne le résultat final (dict).
    """
    import argparse as _ap

    engine = _load_engine()
    run_dir = OUTPUT_BASE / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    t_start = time.time()
    result = {}

    # ── P1 ────────────────────────────────────────────────────────────────────
    _print(f"[ANU | {MODE_NAMES.get(mode_id, '?')}] P1 génération...")
    args_p1 = _ap.Namespace(
        topic=topic, mode=mode_id, pass_id="p1", input=None, run_id=run_id
    )
    result = engine.run_passes(run_dir, args_p1)
    if result.get("status") == "failed":
        return _fail(result, "P1 échouée")
    _print(f"[ANU | {MODE_NAMES.get(mode_id, '?')}] P1 ✅")

    # ── P2 — Audit ────────────────────────────────────────────────────────────
    _print(f"[ANU | {MODE_NAMES.get(mode_id, '?')}] P2 audit...")
    args_p2 = _ap.Namespace(
        topic=topic, mode=mode_id, pass_id="p2",
        input=str(run_dir / "p1.md"), run_id=run_id
    )
    result = engine.run_passes(run_dir, args_p2)
    score = _read_p2_score(run_dir)
    _print(f"[ANU | {MODE_NAMES.get(mode_id, '?')}] P2 score: {score:.1f}/10")

    # ── P3 — Correction conditionnelle ────────────────────────────────────────
    p3_needed = score < 7.0 or result.get("status") == "needs_correction"
    p3_input = str(run_dir / "p1.md")  # fallback

    if p3_needed:
        _print(f"[ANU | {MODE_NAMES.get(mode_id, '?')}] P3 correction (score insuffisant)...")
        args_p3 = _ap.Namespace(
            topic=topic, mode=mode_id, pass_id="p3",
            input=str(run_dir / "p2.md"), run_id=run_id
        )
        result = engine.run_passes(run_dir, args_p3)
        p4_input = str(run_dir / "p3.md")
        _print(f"[ANU | {MODE_NAMES.get(mode_id, '?')}] P3 ✅")
    else:
        _print(f"[ANU | {MODE_NAMES.get(mode_id, '?')}] P3 skipped (score OK)")
        p4_input = str(run_dir / "p2.md")

    # ── P4 — Validation ───────────────────────────────────────────────────────
    _print(f"[ANU | {MODE_NAMES.get(mode_id, '?')}] P4 validation...")
    args_p4 = _ap.Namespace(
        topic=topic, mode=mode_id, pass_id="p4",
        input=p4_input, run_id=run_id
    )
    result = engine.run_passes(run_dir, args_p4)
    _print(f"[ANU | {MODE_NAMES.get(mode_id, '?')}] P4 ✅")

    elapsed = round(time.time() - t_start, 1)
    result["elapsed_s"] = elapsed
    result["score_p2"] = score
    result["mode_id"] = mode_id
    result["mode_name"] = MODE_NAMES.get(mode_id, "?")
    result["p3_executed"] = p3_needed
    result["run_id"] = run_id
    result["run_dir"] = str(run_dir)
    return result


def _read_p2_score(run_dir: Path) -> float:
    """Lit le score moyen depuis p2.json. Retourne 0.0 si absent."""
    p2_json = run_dir / "p2.json"
    if not p2_json.exists():
        return 0.0
    try:
        data = json.loads(p2_json.read_text(encoding="utf-8"))
        score = data.get("score")
        if isinstance(score, dict):
            vals = [v for v in score.values() if isinstance(v, (int, float))]
            return round(sum(vals) / len(vals), 2) if vals else 0.0
        if isinstance(score, (int, float)):
            return float(score)
    except Exception:
        pass
    return 0.0


def _fail(result: dict, msg: str) -> dict:
    result["status"] = "failed"
    result["error"] = msg
    return result


# ── Commandes secondaires ─────────────────────────────────────────────────────
def cmd_status() -> None:
    """Liste les runs récents avec statut."""
    if not OUTPUT_BASE.exists():
        _print("Aucun run ANU trouvé.")
        return
    runs = sorted(OUTPUT_BASE.iterdir(), reverse=True)[:10]
    if not runs:
        _print("Aucun run ANU trouvé.")
        return
    _print(f"{'RUN_ID':<22} {'STATUS':<18} {'PASSES':<8} {'SCORE P2'}")
    _print("-" * 60)
    for run_dir in runs:
        manifest_f = run_dir / ".manifest.json"
        status, passes, score = "?", "-", "-"
        if manifest_f.exists():
            try:
                m = json.loads(manifest_f.read_text())
                status = m.get("status", "?")
                passes = m.get("last_pass", "-")
            except Exception:
                pass
        sc = _read_p2_score(run_dir)
        score = f"{sc:.1f}" if sc > 0 else "-"
        _print(f"{run_dir.name:<22} {status:<18} {passes:<8} {score}")


def cmd_resume(run_id: str, topic: str, mode_id: int) -> dict:
    """
    Reprend un run depuis le dernier checkpoint valide.
    TODO: Hermes — détecter la dernière passe réussie et passer start_pass
    """
    run_dir = OUTPUT_BASE / run_id
    if not run_dir.exists():
        _print(f"Run introuvable : {run_id}")
        sys.exit(1)

    # Détecter la dernière passe réussie
    last_pass = "p1"
    for p in ["p4", "p3", "p2", "p1"]:
        ck = run_dir / f"{p}.json"
        if ck.exists():
            try:
                data = json.loads(ck.read_text())
                if data.get("status") == "completed":
                    last_pass = p
                    break
            except Exception:
                pass

    pass_map = {"p1": "p2", "p2": "p3", "p3": "p4", "p4": "done"}
    next_pass = pass_map.get(last_pass, "done")
    if next_pass == "done":
        _print(f"[ANU] Run {run_id} déjà complet (P4 OK).")
        return {"status": "already_complete", "run_id": run_id}

    _print(f"[ANU] Reprise run {run_id} depuis {next_pass} (dernière passe OK : {last_pass})")
    return run_pipeline(topic, mode_id, run_id, start_pass=next_pass)


# ── Livraison résultat ────────────────────────────────────────────────────────
def deliver(result: dict) -> None:
    """Lit p4.md et l'affiche comme réponse principale."""
    run_dir = Path(result.get("run_dir", ""))
    p4_md = run_dir / "p4.md"
    output_file = result.get("output_file", "")

    content = ""
    for candidate in [p4_md, Path(output_file) if output_file else None]:
        if candidate and candidate.exists():
            content = candidate.read_text(encoding="utf-8").strip()
            break

    if not content:
        _print("[ANU] Aucun contenu p4.md disponible.")
        return

    _print("\n" + "═" * 60)
    _print(f"[ANU] {result.get('mode_name','?')} | run: {result.get('run_id','')}")
    _print(f"      Score P2: {result.get('score_p2', 0):.1f}/10 "
           f"| P3: {'✅' if result.get('p3_executed') else 'skipped'} "
           f"| Durée: {result.get('elapsed_s', '?')}s")
    _print("═" * 60 + "\n")
    _print(content)
    _print("\n" + "─" * 60)
    _print(f"[ANU] run_id: {result.get('run_id','')} — {run_dir}")

    _log_autonomous(
        f"run_id={result.get('run_id')} mode={result.get('mode_name')} "
        f"score_p2={result.get('score_p2')} elapsed={result.get('elapsed_s')}s "
        f"p3={'yes' if result.get('p3_executed') else 'no'} "
        f"status={result.get('status')}"
    )


# ── Help ──────────────────────────────────────────────────────────────────────
HELP = """
/anu — ANU Mind Think-Tank

Usage:
  /anu <topic>              Analyse avec détection automatique du mode
  /anu <topic> --mode N     Force l'archétype (1-7)
  /anu --resume <run_id>    Reprend un run interrompu
  /anu --status             Liste les 10 derniers runs
  /anu --help               Affiche cette aide

Archétypes:
  1 ARCHITECT  — architecture, système, infrastructure
  2 CODER      — code, debug, script (défaut)
  3 TEACHER    — documentation, tutoriel, explication
  4 PROTOCOL   — procédure, spec, workflow
  5 AUDITOR    — audit, sécurité, risque
  6 WRITER     — rédaction, rapport, synthèse
  7 RESEARCHER — recherche, comparaison, faits

Exemples:
  /anu analyse la stack réseau
  /anu implémente un rate limiter --mode 2
  /anu sécurité SSH --mode 5
  /anu --resume 20260718_143022
  /anu --status
"""


# ── Main ──────────────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("topic", nargs="*", help="Sujet à analyser")
    parser.add_argument("--mode", type=int, choices=range(1, 8), default=None)
    parser.add_argument("--resume", type=str, default=None, metavar="RUN_ID")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--help", "-h", action="store_true")
    args = parser.parse_args(argv)

    if args.help or (not args.topic and not args.resume and not args.status):
        _print(HELP)
        return

    if args.status:
        cmd_status()
        return

    # Vérification prérequis
    errors = check_prerequisites()
    if errors:
        for e in errors:
            _print(f"[ANU] ERREUR : {e}")
        sys.exit(1)

    topic = " ".join(args.topic) if args.topic else ""
    mode_id = args.mode or detect_mode(topic)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    _print(f"[ANU] Démarrage | mode: {MODE_NAMES.get(mode_id, '?')} ({mode_id}) | run: {run_id}")
    _log_autonomous(f"start run_id={run_id} mode={mode_id} topic={topic[:80]!r}")

    if args.resume:
        result = cmd_resume(args.resume, topic, mode_id)
    else:
        result = run_pipeline(topic, mode_id, run_id)

    if result.get("status") == "failed":
        _print(f"[ANU] Échec : {result.get('error', 'inconnu')}")
        _log_autonomous(f"FAILED run_id={run_id} error={result.get('error')}")
        sys.exit(1)

    deliver(result)


if __name__ == "__main__":
    main()
