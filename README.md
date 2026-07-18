# ANU Mind

> Moteur de raisonnement structuré multi-passes pour **Hermes Agent**.  
> Déclenché via la slash command `/anu`, il améliore la qualité et la pertinence des réponses sur des sujets complexes en appliquant un pipeline 4 passes : génération → audit → correction → validation.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Stdlib only](https://img.shields.io/badge/deps-stdlib%20only-4caf50)]()
[![Hermes Skill](https://img.shields.io/badge/Hermes-Skill-purple)]()
[![Status](https://img.shields.io/badge/Status-ACTIF-brightgreen)]()
[![License](https://img.shields.io/badge/License-MIT-lightgrey)]()

---

## Principe

ANU n'est pas un modèle différent — c'est une **méthode d'utilisation structurée** du même LLM (Stepfun 3.7 flash via Hermes) en 4 étapes séquentielles et contrôlées.

```
Utilisateur : /anu <topic>
                  │
            ┌─────▼──────┐
            │  P1 : GEN  │  Génération initiale (archétype choisi)
            └─────┬──────┘
            ┌─────▼──────┐
            │  P2 : AUDIT│  Critique + scoring 5 dimensions (0-10)
            └─────┬──────┘
             score < 7 ?
            ┌─────▼──────┐
            │  P3 : FIX  │  Correction ciblée (si nécessaire)
            └─────┬──────┘
            ┌─────▼──────┐
            │  P4 : VAL  │  Validation finale
            └─────┬──────┘
              Livraison p4.md
```

---

## Structure du dépôt

```
anu/
├── tool/
│   ├── anu_tool.py          ← Implémentation slash command /anu
│   ├── tool_definition.json ← Déclaration Hermes du tool
│   └── README.md
├── scripts/
│   └── engine.py            ← Moteur 4-passes (544 lignes, stdlib only)
├── references/
│   ├── anu-slash-command.md ← Référence complète /anu
│   ├── modes.md             ← Spécifications 7 archétypes
│   ├── stepfun-nous-backend.md
│   ├── nous-model-naming.md
│   ├── provider-backend.md
│   └── ns-documentation.md
├── templates/
│   └── checkpoint_v1.json   ← Schéma checkpoint par passe
├── tests/
│   ├── test_anu_tool.py     ← Tests unitaires (detect_mode, score)
│   ├── test_engine_integration.py ← Tests intégration (skip si pas de LLM)
│   └── conftest.py
├── backups/                 ← Snapshots horodatés engine.py
├── SKILL.md                 ← Définition skill Hermes
└── README.md
```

---

## Usage

### Slash command (point d'entrée canonique)

```
/anu <topic>              # mode auto-détecté selon le sujet
/anu <topic> --mode N     # archétype forcé (1-7)
/anu --resume <run_id>    # reprise depuis dernier checkpoint valide
/anu --status             # liste 10 derniers runs
/anu --help               # aide
```

### Exemples

```
/anu analyse la stack réseau Proxmox
/anu implémente un rate limiter Python --mode 2
/anu sécurité SSH — hardening VM Debian --mode 5
/anu --resume 20260718_143022
/anu --status
```

### Progression en temps réel

```
[ANU | ARCHITECT] P1 génération...
[ANU | ARCHITECT] P1 ✅
[ANU | ARCHITECT] P2 audit...
[ANU | ARCHITECT] P2 score: 7.8/10
[ANU | ARCHITECT] P3 skipped (score OK)
[ANU | ARCHITECT] P4 validation... ✅
[ANU] Terminé en 47s — run_id: 20260718_143022
```

---

## Archétypes (7 modes)

| ID | Nom | Domaine | Température |
|---|---|---|---|
| 1 | ARCHITECT | Architecture, infrastructure, design | basse |
| 2 | CODER | Code, debug, scripts (**défaut**) | basse |
| 3 | TEACHER | Documentation, tutoriels, explications | moyenne |
| 4 | PROTOCOL | Procédures, specs, workflows | très basse |
| 5 | AUDITOR | Sécurité, audit, risques | très basse |
| 6 | WRITER | Rédaction, rapports, synthèses | haute |
| 7 | RESEARCHER | Recherche, comparaisons, faits | basse |

Détail complet : `references/modes.md`

---

## Score P2 — Dimensions d'audit

| Dimension | Description |
|---|---|
| `factualite` | Exactitude des faits (0-10) |
| `couverture` | Exhaustivité du traitement (0-10) |
| `coherence` | Cohérence logique interne (0-10) |
| `risques` | Identification des risques ou angles manquants (0-10) |
| `clarte` | Clarté et lisibilité (0-10) |

Si la moyenne < 7.0 ou si une dimension est `critical_low` → P3 (correction) est déclenchée automatiquement.

---

## Architecture technique

### `tool/anu_tool.py`

Implémentation de la slash command `/anu` :

- `main()` — point d'entrée, parsing args, routage
- `detect_mode(topic)` — mapping topic → archétype par mots-clés
- `check_prerequisites()` — vérifie que `engine.py` est accessible
- `run_pipeline(topic, mode_id, run_id)` — orchestre P1→P2→P3?→P4
- `cmd_resume(run_id, ...)` — reprise depuis dernier checkpoint valide
- `cmd_status()` — liste des 10 derniers runs
- `deliver(result)` — lecture et affichage de `p4.md`
- `_log_autonomous(msg)` — journalisation dans `hermes_YYYY-MM-DD.log`

### `scripts/engine.py`

Moteur bas niveau (544 lignes, stdlib uniquement) :

- Authentification OAuth2 Hermes (`auth.json` + `config.yaml`)
- Résolution modèle/endpoint (`_resolved_model`, `_resolved_base_url`)
- Appel LLM avec extraction `content → reasoning → reasoning_details`
- Écriture atomique des checkpoints (write + rename)
- Calcul score P2 par dimension
- Refresh token automatique sur 401/403

### Flux de données

```
/anu topic --mode N
    │
    ├── anu_tool.py : detect_mode() → run_id
    │
    ├── engine.run_passes(run_dir, args_p1)   → p1.md + p1.json
    ├── engine.run_passes(run_dir, args_p2)   → p2.md + p2.json (score)
    ├── [engine.run_passes(run_dir, args_p3)] → p3.md + p3.json (si score < 7)
    ├── engine.run_passes(run_dir, args_p4)   → p4.md + p4.json
    │
    └── deliver(result) → affichage p4.md + résumé
```

---

## Intégration dans Hermes

### Installation

```bash
# Copier dans le répertoire skills Hermes
cp -r . ~/.hermes/skills/autonomous-ai-agents/anu-mind/

# Vérifier que le tool est détecté
hermes tools list | grep anu
```

### SOUL.md — Section à ajouter dans les directives Hermes

```
## Tool /anu — ANU Mind

/anu est le seul point d'entrée du pipeline ANU.
Ne jamais appeler engine.py directement sans passer par /anu.
Ne jamais déclencher ANU sans invocation explicite /anu.

En cas d'erreur LLM pendant un run : checkpoint sur la dernière passe
réussie, notifier l'utilisateur, proposer --resume <run_id>.
```

### Répertoire de sortie

```
~/.hermes/profiles/<profile>/cron/output/anu/<run_id>/
├── p1.md / p1.json
├── p2.md / p2.json
├── p3.md / p3.json   (si correction)
├── p4.md / p4.json   ← livrable principal
└── .manifest.json
```

---

## Tests

```bash
# Tests unitaires (sans LLM)
python3 -m pytest tests/test_anu_tool.py -v

# Tests d'intégration (nécessitent un backend LLM actif)
python3 -m pytest tests/test_engine_integration.py -m integration -v

# Tous les tests
python3 -m pytest -v
```

---

## Sécurité

- Aucun token/secret en clair dans le code, les checkpoints ou les logs
- `scrub_secrets()` appliqué sur toute sortie LLM avant écriture disque
- Pas d'`eval()`, `exec()`, `subprocess` avec input utilisateur
- Inputs : `topic` et `--mode` uniquement

---

## Changelog

### v2.0.0 — Juillet 2026

- **[arch]** Ajout slash command `/anu` (`tool/anu_tool.py` + `tool_definition.json`)
- **[arch]** `engine.py` n'est plus invocable directement depuis une session Hermes
- **[impl]** `detect_mode()` — mapping automatique topic → archétype
- **[impl]** `run_pipeline()` — orchestration P1→P2→P3?→P4 avec score conditionnel
- **[impl]** `cmd_resume()` — reprise depuis dernier checkpoint valide
- **[impl]** `cmd_status()` — listing des runs récents
- **[impl]** `_log_autonomous()` — journalisation AUTONOMOUS native
- **[test]** `tests/test_anu_tool.py` — 9 tests unitaires (detect_mode, score)
- **[test]** `tests/test_engine_integration.py` — tests intégration LLM
- **[docs]** `references/anu-slash-command.md` — référence complète /anu
- **[docs]** `SKILL.md` v2.0.0 — mis à jour, /anu comme point d'entrée canonique

### v1.0.0 — Juin 2026

- Pipeline 4 passes initial (`engine.py`)
- 7 archétypes, checkpoints JSON, scoring P2
- Intégration Hermes via `execute_code`

---

## Mainteneur

**Pytheas Infrastructure** — Usage interne exclusif.  
Architecture : **Claude (Anthropic)** via MCP GitHub.  
Implémentation : **Hermes** (Stepfun 3.7 flash, profil dev) depuis pytheas.

<div align="center">
  <sub>Composant de l'écosystème <strong>Hermes</strong> — Pytheas Infrastructure 🌿</sub>
</div>
