# ANU Mind

> Moteur de raisonnement structuré multi-passes pour **Hermes Agent**.  
> Déclenché via la commande `anu` ou le slash `/anu`, il améliore la qualité des réponses sur des sujets complexes en appliquant un pipeline 4 passes : génération → audit → correction (conditionnelle) → validation.  
> Wrapper Telegram `anu-tg` fourni via liens symboliques système pointant vers `install/`.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Stdlib only](https://img.shields.io/badge/deps-stdlib%20only-4caf50)]()
[![Hermes Skill](https://img.shields.io/badge/Hermes-Skill-purple)]()
[![Status](https://img.shields.io/badge/Status-ACTIF%20PROD-brightgreen)]()

---

## Principe

ANU n’est pas un modèle différent — c’est une **méthode d’utilisation structurée** du même LLM (Stepfun 3.7 flash via Hermes) en 4 étapes séquentielles et contrôlées.

```
anu <topic>
       │
  P1 ┃ Génération initiale (archétype choisi)
       │
  P2 ┃ Audit + scoring 5 dimensions (0-10)
       │
  P3 ┃ Correction ciblée — uniquement si score < 7.0 ou dimension < 5
       │
  P4 ┃ Validation finale → livrable p4.md
```

---

## Structure du dépôt

```
anu/
├── tool.py                       ← Point d’entrée prod (→ ~/.local/bin/anu)
├── scripts/
│   └── engine.py                  ← Moteur 4-passes (stdlib only)
├── install/
│   ├── anu-tg.sh                  ← Wrapper Telegram déployé via installer
│   └── install.sh                 ← Déploiement idempotent des symlinks
├── references/
│   ├── modes.md                   ← Spécifications 7 archétypes
│   ├── stepfun-nous-backend.md
│   ├── nous-model-naming.md
│   ├── provider-backend.md
│   └── ns-documentation.md
├── templates/
│   └── checkpoint_v1.json         ← Schéma checkpoint par passe
├── tests/                         ← Tests unitaires et intégration
├── backups/                       ← Snapshots horodatés engine.py
├── SKILL.md                       ← Définition skill Hermes
└── README.md
```

> **Note :** `tool/` (anu_tool.py, tool_definition.json) est le squelette architecte Claude (référence).  
> `tool.py` à la racine est l’implémentation réelle en production.

### Déploiement système

```bash
# Installer/mettre à jour les liens système depuis le dépôt
bash install/install.sh

# Résultat attendu
# ~/.local/bin/anu        → <repo>/tool.py
# ~/.local/bin/anu-tg     → <repo>/install/anu-tg.sh
```

`install.sh` est idempotent :
- `mkdir -p ~/.local/bin`
- `ln -snf` pour forcer l’écrasement sans déréférencement
- `chmod +x` sur source et cibles

---

## Usage

```bash
anu <topic>                # mode auto-détecté
anu <topic> --mode N      # archétype forcé (1-7)
anu <topic> --detach      # exécution arrière-plan + callback Telegram
anu --resume <run_id>     # reprise pipeline complet depuis dernier checkpoint
anu --status              # liste 20 derniers runs
```

> **Manuel utilisateur FR :** `docs/manuel_utilisation_fr.md`

### Exemples

```bash
anu "audit SSH hardening" --mode 5
anu "refactor parser.py" --mode 2
anu "architecture NAS backup" --mode 1 --detach
anu --status
anu --resume 20260719_132400
```

---

## Modes (archétypes)

| Mode | Nom | Domaine | Détection auto |
|---|---|---|---|
| 1 | ARCHITECT | Architecture, infrastructure | `architecture`, `design`, `schema`, `stack` |
| 2 | CODER | Code, debug, scripts (**défaut**) | `code`, `debug`, `script`, `refactor` |
| 3 | TEACHER | Documentation, tutoriels | `explique`, `tutoriel`, `documentation` |
| 4 | PROTOCOL | Procédures, specs, workflows | `procedure`, `spec`, `protocole`, `yaml` |
| 5 | AUDITOR | Sécurité, audit, risques | `audit`, `securite`, `risque` |
| 6 | WRITER | Rédaction, rapports | `redige`, `article`, `rapport` |
| 7 | RESEARCHER | Recherche, comparaisons | `recherche`, `compare`, `benchmark` |

---

## Pipeline détaillé

### Règles d’exécution

| Passe | Condition | Toujours |
|---|---|---|
| P1 | — | ✅ |
| P2 | — | ✅ |
| P3 | `mean < 7.0` OU dimension `< 5` | Non (conditionnel) |
| P4 | — | ✅ |

### Score P2 — 5 dimensions

| Dimension | Description |
|---|---|
| `factualite` | Exactitude des faits (0-10) |
| `couverture` | Exhaustivité (0-10) |
| `coherence` | Cohérence logique (0-10) |
| `risques` | Identification des risques (0-10) |
| `clarte` | Lisibilité (0-10) |

### Artefacts par run

```
~/.hermes/profiles/<profile>/cron/output/anu/<run_id>/
├── p1.md / p1.json
├── p2.md / p2.json   ← score 5 dimensions
├── p3.md / p3.json   ← si correction nécessaire
├── p4.md / p4.json   ← livrable principal
└── .manifest.json    ← écriture atomique (.tmp + os.replace)
```

---

## Mode `--detach` (arrière-plan)

- Fork via `systemd-run --user --unit=anu-run-<run_id>`
- Retour shell garanti < 2 s
- Callback Telegram automatique à la fin : livrable `p4.md` fragmenté en chunks ≤ 4096 caractères
- Environnement injecté : `XDG_RUNTIME_DIR`, `DBUS_SESSION_BUS_ADDRESS`, `HERMES_HOME`, `HERMES_PROFILE`, `HOME`, `USER`

### Format callback Telegram

```
[ANU | ARCHITECT | Run 20260719_132400 | Score P2: 8.2/10]
<contenu p4.md>
```

---

## Variables d’environnement

| Variable | Défaut | Rôle |
|---|---|---|
| `HERMES_PROFILE` | `dev` | Profile Hermes actif |
| `HERMES_HOME` | `~/.hermes` | Racine Hermes |
| `TELEGRAM_BOT_TOKEN` | — | Override token (prioritaire sur auth.json) |
| `TELEGRAM_CHAT_ID` | — | Override chat_id |

**Lecture des credentials Telegram (priorité décroissante) :**
1. Env vars `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`
2. `~/.hermes/auth.json` → `providers.telegram`
3. `~/.hermes/config.yaml` → section `telegram:`

---

## Installation

```bash
# Le skill est déjà installé via Hermes
# Points d’entrée :
ls -la ~/.local/bin/anu ~/.local/bin/anu-tg
# ~/.local/bin/anu       → <repo>/tool.py
# ~/.local/bin/anu-tg    → <repo>/install/anu-tg.sh

# Installer/mettre à jour les liens :
bash <repo>/install/install.sh

# Vérification
anu --help
anu --status
```

---

## Logging

```
~/.hermes/profiles/<profile>/logs/hermes_YYYY-MM-DD.log
```

Événements tracés (`[AUTONOMOUS] [anu_mind]`) :

| Événement | Description |
|---|---|
| `run_start` | Début run synchrone |
| `run_start_detach` | Début run détaché |
| `run_completed` | Fin OK avec score et nb passes |
| `run_failed` | Erreur avec traceback |
| `run_resume` | Reprise depuis checkpoint |
| `telegram_push_start` | Tentative envoi (token masqué) |
| `telegram_push_failed` | Échec envoi avec raison |

---

## Sécurité

- Token Telegram **jamais en clair dans les logs** (`_mask_token()` — format `abcd****...wxyz`)
- Aucun secret dans les checkpoints ou artefacts de run
- Inputs : `topic` et `--mode` uniquement
- Pas d’`eval()`, `exec()`, `subprocess` avec input utilisateur

---

## Limitations connues

- Erreur bash `impossible de régler le groupe de processus du terminal` : attendue hors terminal de contrôle, sans impact fonctionnel
- `auth.json` absent/corrompu : callbacks Telegram désactivés, tracé en `credentials_missing`
- `PROFILE` absent depuis un shell brut : repli automatique sur `dev`

---

## Changelog

### v2.0.2 — Juillet 2026

- **[feat]** Ajout de `install/install.sh` avec déploiement idempotent des symlinks
- **[feat]** Intégration du wrapper `anu-tg` dans le dépôt via `install/anu-tg.sh`
- **[maint]** Single Source of Truth étendue aux binaires système `anu` et `anu-tg`

### v2.0.1 — Juillet 2026 (patch prod)

- **[fix]** `response.status` (corrige `resp.status` — NameError, Telegram toujours échoué)
- **[fix]** `DEFAULT_RUN_ROOT` / `ENGINE_DEFAULT` respectent `HERMES_PROFILE` env var
- **[fix]** `_resume()` : reprise complète du pipeline depuis le dernier checkpoint (pas seulement la passe suivante)
- **[fix]** Token Telegram masqué dans tous les appels `_log_line()`
- **[fix]** `_load_telegram_credentials()` : regex YAML plus robuste, suppression du fallback `openrouter`
- **[maint]** `.gitignore` : exclusion des `.bak` et des runs Hermes
- **[docs]** README aligné sur l’implémentation réelle

### v2.0.0 — Juillet 2026

- Pipeline 4 passes avec mode `--detach` (systemd-run) et callback Telegram
- 7 archétypes, détection automatique par mots-clés
- Manifest atomique, logging AUTONOMOUS
- `--status` et `--resume`

### v1.0.0 — Juin 2026

- Pipeline 4 passes initial (`engine.py`)
- Intégration Hermes via `execute_code`

---

## Mainteneur

**Pytheas Infrastructure** — Usage interne exclusif.  
Architecture : **Claude (Anthropic)** via MCP GitHub.  
Implémentation : **Hermes** (Stepfun 3.7 flash, profil dev) depuis pytheas.

<div align="center">
  <sub>Composant de l’écosystème <strong>Hermes</strong> — Pytheas Infrastructure 🌿</sub>
</div>
