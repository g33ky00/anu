# /anu — Référence Slash Command

## Déclenchement

Le tool `/anu` est le **seul point d'entrée autorisé** pour le pipeline ANU Mind.  
Ne jamais appeler `scripts/engine.py` directement depuis une session Hermes.

## Syntaxe

```
/anu <topic>                   # mode auto-détecté
/anu <topic> --mode N          # archétype forcé (1-7)
/anu --resume <run_id>         # reprise depuis dernier checkpoint valide
/anu --status                  # 10 derniers runs avec statut
/anu --help                    # aide
```

## Mapping automatique topic → archétype

| Mode | Archétype | Mots-clés déclencheurs |
|---|---|---|
| 1 | ARCHITECT | architecture, système, infrastructure, design, schéma |
| 2 | CODER | code, debug, script, fonction, implémente, refactor |
| 3 | TEACHER | explique, tutoriel, apprends, documentation, guide |
| 4 | PROTOCOL | procédure, spec, protocole, workflow, yaml, json |
| 5 | AUDITOR | audit, sécurité, risque, vulnérabilité, analyse |
| 6 | WRITER | rédige, écris, article, rapport, résumé, synthèse |
| 7 | RESEARCHER | recherche, compare, évalue, benchmark, faits |

Fallback : mode 2 (CODER) si aucun match.

## Flux d'exécution

```
/anu <topic> [--mode N]
        │
        ├─ check_prerequisites()       # engine.py accessible ?
        ├─ detect_mode(topic)          # si --mode absent
        ├─ run_id = YYYYMMDD_HHMMSS
        │
        ├─ P1 : génération initiale
        ├─ P2 : audit + scoring 5 dimensions
        │       score < 7.0 ─── oui ──→ P3 correction
        │           │                        │
        │          non                       │
        │           │                        ▼
        └─ P4 : validation finale ◄──────────┘
                │
                └─ Livraison p4.md + résumé (score, durée, run_id)
```

## Notifications de progression

```
[ANU | ARCHITECT] P1 génération...
[ANU | ARCHITECT] P1 ✅
[ANU | ARCHITECT] P2 audit...
[ANU | ARCHITECT] P2 score: 7.8/10
[ANU | ARCHITECT] P3 skipped (score OK)
[ANU | ARCHITECT] P4 validation...
[ANU | ARCHITECT] P4 ✅
[ANU] Terminé en 47s — run_id: 20260718_143022
```

## Reprise (`--resume`)

Si un run est interrompu (timeout, erreur LLM, rate limit) :

```bash
/anu --resume 20260718_143022
# Détecte la dernière passe OK et reprend depuis la suivante
```

## Répertoire de sortie

```
~/.hermes/profiles/<profile>/cron/output/anu/<run_id>/
├── p1.md / p1.json
├── p2.md / p2.json      # contient scores 5 dimensions
├── p3.md / p3.json      # si correction nécessaire
├── p4.md / p4.json      # livrable principal
└── .manifest.json       # agrégat toutes passes
```

## Règles de gouvernance

- Ne jamais déclencher ANU sans invocation explicite `/anu`
- En cas d'erreur LLM pendant un run : checkpoint sur dernière passe réussie, proposer `--resume`
- Maximum 3 passes de correction (P3) pour éviter les boucles
- Aucun secret/API key en clair dans les fichiers de run (`scrub_secrets()` appliqué)
- Logger chaque session en `AUTONOMOUS` dans `hermes_YYYY-MM-DD.log`
