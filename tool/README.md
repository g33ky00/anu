# tool/ — /anu Slash Command

Point d'entrée unique du pipeline ANU Mind.

## Fichiers

| Fichier | Rôle |
|---|---|
| `anu_tool.py` | Implémentation du tool `/anu` |
| `tool_definition.json` | Déclaration Hermes du tool (trigger, args, toolsets) |

## Installation dans Hermes

```bash
# Depuis le répertoire du skill anu-mind :
hermes skills install .
# ou copier dans ~/.hermes/skills/autonomous-ai-agents/anu-mind/
```

## Usage

```
/anu <topic>              # auto-détection du mode
/anu <topic> --mode N     # archétype forcé (1-7)
/anu --resume <run_id>    # reprise depuis dernier checkpoint
/anu --status             # liste 10 derniers runs
/anu --help               # aide
```

## Variables d'environnement

| Variable | Défaut | Rôle |
|---|---|---|
| `HERMES_PROFILE` | `dev` | Profile Hermes actif |
| `HERMES_HOME` | `~/.hermes` | Répertoire home Hermes |
| `THAECREATIONS_PROFILE` | — | Override profile (gateway thaecreations) |

## TODO: Hermes

- `check_prerequisites()` : ajouter smoke test `llm_generate()`
- `detect_mode()` : améliorer avec scoring pondéré si pertinent
- Intégrer `get_logger()` Hermes si disponible dans le contexte d'exécution
