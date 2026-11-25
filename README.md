# ANU Mind


## About

Project description.

> Moteur de raisonnement structuré multi-passes pour **Hermes Agent**.
> Déclenché via la commande `anu`, il améliore la qualité des réponses sur des sujets complexes
> en appliquant un pipeline 4 passes : génération → audit → correction (conditionnelle) → validation.
> Callback automatique via Telegram à l'issue de chaque run détaché.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Stdlib only](https://img.shields.io/badge/deps-stdlib%20only-4caf50)]()
[![Hermes Skill](https://img.shields.io/badge/Hermes-Skill-purple)]()
[![Version](https://img.shields.io/badge/version-1.0.1-blue)]()
[![Status](https://img.shields.io/badge/Status-PROD-brightgreen)]()

---

## Principe

ANU n’est pas un modèle différent — c’est une **méthode d’utilisation structurée** du même LLM
(Stepfun 3.7 flash via Hermes) en 4 étapes séquentielles et contrôlées.

```
anu "<topic>"
       │
  P1 ┃ Génération initiale (archétype choisi)
       │
  P2 ┃ Audit + scoring 5 dimensions (0-10)
       │
  P3 ┃ Correction ciblée — uniquement si mean < 7.0 OU dimension < 5
       │                    timeout volontaire à 600s (phase longue)
  P4 ┃ Validation finale → livrable p4.md
       │
       └── Callback Telegram automatique (mode --detach)
```

---

## Structure du dépôt

```
anu/
├── tool.py                          ← Point d’entrée prod (symlink ~/.local/bin/anu)
├── install.sh                       ← Installe anu-tg dans ~/.local/bin
├── install/
│   └── anu-tg.sh                    ← Wrapper shell : anu + --detach + chat_id
├── scripts/
│   ├── engine.py                    ← Moteur 4 passes (stdlib only)
│   └── patch_auth.py                ← Utilitaire patch auth.json (maintenance)
├── references/
│   ├── architecture.md              ← Architecture technique détaillée
│   ├── modes.md                     ← Spécifications 7 archétypes
│   ├── anu-slash-command.md
│   ├── stepfun-nous-backend.md
│   ├── provider-backend.md
│   ├── nous-model-naming.md
│   ├── ns-documentation.md
│   └── run_passes-return-none-diagnosis.md
├── docs/
│   └── manuel_utilisation_fr.md    ← Manuel utilisateur complet (FR)
├── templates/
│   └── checkpoint_v1.json
├── backups/
├── tests/
├── SKILL.md
└── README.md
```

> `tool/` contient le squelette architecte Claude (référence).
> `tool.py` à la racine est l’implémentation réelle en production.

---

## Installation

```bash
# Symlink anu → tool.py (déjà effectué sur pytheas)
~/.local/bin/anu → /home/g33ky/.hermes/skills/autonomous-ai-agents/anu-mind/tool.py

# Installer anu-tg (wrapper Telegram)
./install.sh
# Crée : ~/.local/bin/anu-tg → install/anu-tg.sh
```

---

## Usage

### Commande `anu`

```bash
anu "<topic>"                     # mode auto-détecté, cold start
anu "<topic>" --mode N            # archétype forcé (1-7)
anu "<topic>" --detach            # exécution arrière-plan + callback Telegram
anu --resume <run_id>             # reprise pipeline depuis dernier checkpoint
anu --status                      # liste 20 derniers runs
```

### Wrapper `anu-tg`

```bash
anu-tg "<topic>"                  # mode TEACHER + detach + callback Telegram
anu-tg "<topic>" <chat_id>        # override chat_id destination
```

### Exemples

```bash
anu "audit SSH hardening" --mode 5
anu "refactor parser.py" --mode 2
anu "architecture NAS backup" --mode 1 --detach
anu --status
anu --resume 20260719_132400
anu-tg "explique le protocole BGP"
```

---

## Modes (archétypes)

| Mode | Nom | Domaine | Temp. | Max tokens | Détection auto |
|---|---|---|---|---|---|
| 1 | ARCHITECT | Architecture, infrastructure, design | 0.7 | 8192 | `architecture`, `design`, `schema`, `stack` |
| 2 | CODER | Code, debug, scripts (**défaut**) | 0.2 | 8192 | `code`, `debug`, `script`, `refactor`, `bug` |
| 3 | TEACHER | Documentation, tutoriels, explications | 0.6 | 8192 | `explique`, `tutoriel`, `documentation` |
| 4 | PROTOCOL | Procédures, specs, workflows | 0.0 | 4096 | `procedure`, `spec`, `protocole`, `yaml` |
| 5 | AUDITOR | Sécurité, audit, risques | 0.3 | 4096 | `audit`, `securite`, `risque` |
| 6 | WRITER | Rédaction, rapports, synthèses | 0.8 | 8192 | `redige`, `article`, `rapport` |
| 7 | RESEARCHER | Recherche, comparaisons, faits | 0.2 | 8192 | `recherche`, `compare`, `benchmark` |

Fallback si aucun match : mode 2 (CODER).
Mode 3 (TEACHER) : détection par mot entier (`\b`) — prioritaire sur les autres.

---

## Pipeline détaillé

### Règles d’exécution

| Passe | Rôle | Condition | Timeout |
|---|---|---|---|
| P1 | Génération initiale | Toujours | 600s |
| P2 | Audit + scoring 5 dimensions | Toujours | 600s |
| P3 | Correction ciblée | `mean < 7.0` OU dimension `< 5` | **600s (volontaire)** |
| P4 | Validation finale | Toujours | 600s |

Le timeout P3 à 600 secondes est intentionnel.

### Score P2 — 5 dimensions

| Dimension | Description |
|---|---|
| `factualite` | Exactitude des faits (0-10) |
| `couverture` | Exhaustivité (0-10) |
| `coherence` | Cohérence logique (0-10) |
| `risques` | Identification des risques (0-10) |
| `clarte` | Lisibilité (0-10) |

`mean >= 7.0` ET aucune dimension `< 5` → P3 skipped, passage direct à P4.
Plafond anti-boucle : 3 passes P3 maximum (`MAX_CORRECTION_PASSES = 3`).

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
- Retour shell < 2 s garanti
- Callback Telegram automatique à la fin (succès ou échec)
- Environnement injecté via `--setenv` : `TELEGRAM_CHAT_ID`, `TELEGRAM_BOT_TOKEN`, `PROFILE`, `HERMES_HOME`, `PATH`

### Format callback Telegram

**Succès :**
```
[ANU | ARCHITECT | Run 20260719_132400 | Score P2: 8.2/10]
<contenu p4.md — fragmenté en chunks ≤ 4096 caractères>
```

**Échec :**
```
🚨 [ANU - ERREUR FATALE] Échec pipeline.
Reprise : /anu --resume 20260719_132400
Erreur : <détail>
```

---

## Wrapper `anu-tg`

```bash
# Ce que fait anu-tg :
export TELEGRAM_CHAT_ID="${2:-$DEFAULT_CHAT_ID}"   # -5380549950 par défaut
anu "$1" --mode 3 --detach                          # mode TEACHER, arrière-plan
```

`DEFAULT_CHAT_ID` est défini dans `install/anu-tg.sh`.

---

## Variables d’environnement

| Variable | Défaut | Rôle |
|---|---|---|
| `HERMES_PROFILE` | `dev` | Profile Hermes actif |
| `PROFILE` | `dev` | Alias HERMES_PROFILE (compatibilité) |
| `HERMES_HOME` | `~/.hermes/profiles/<profile>` | Racine Hermes du profil |
| `TELEGRAM_BOT_TOKEN` | — | Override token (prioritaire sur auth.json) |
| `TELEGRAM_CHAT_ID` | — | Override chat_id destination |

**Lecture des credentials Telegram (priorité décroissante) :**

1. Env vars `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`
2. `HERMES_HOME/profiles/<profile>/auth.json` → `providers.telegram`
3. `~/.hermes/auth.json` → `providers.telegram` (fallback global)
4. `HERMES_HOME/config.yaml` → section `telegram:`

---

## Logging

```
~/.hermes/profiles/<profile>/logs/hermes_YYYY-MM-DD.log
```

(`DEFAULT_LOG_DIR = _HERMES_HOME / "logs"` — fix v1.0.1)

Événements tracés (`[AUTONOMOUS] [anu_mind]`) :

| Événement | Description |
|---|---|
| `run_start` | Début run synchrone |
| `run_start_detach` | Début run détaché |
| `run_completed` | Fin OK — score P2 + nb passes |
| `run_failed` | Erreur avec détail |
| `run_resume` | Reprise depuis checkpoint |
| `telegram_push_start` | Tentative envoi |
| `telegram_push_success` | Envoi confirmé |
| `telegram_push_failed` | Échec avec raison |
| `telegram_credentials_diag` | Diagnostic credentials manquants |

---

## Sécurité

- Token Telegram **jamais en clair dans les logs** (`_mask_token()` → `abcd****...wxyz`)
- `scrub_secrets()` appliqué sur toute sortie LLM avant écriture disque
- Aucun secret dans les checkpoints ou artefacts de run
- Inputs : `topic` et `--mode` uniquement

---

## Limitations connues

- Erreur bash `impossible de régler le groupe de processus du terminal` : attendue hors terminal de contrôle, sans impact fonctionnel.
- `auth.json` absent/corrompu : callbacks Telegram désactivés, tracé `credentials_missing`.
- `PROFILE` absent depuis shell brut : repli automatique sur `dev`.
- `ENGINE_DEFAULT` : path absolu `/home/g33ky/.hermes/...` (dette migratoire N4, documentée).

---

## Changelog

### v1.0.1 — 23 juillet 2026

- **[fix]** Chemin log corrigé : `DEFAULT_LOG_DIR = _HERMES_HOME / "logs"` (suppression du doublon `profiles/<profile>` qui résultait en path invalide)
- **[fix]** Retrait de `--context` : feature non implémentée retirée du code et de la documentation
- **[maint]** Versions harmonisées `v1.0.x` dans l’entièreté du dépôt (suppression des références `v2.0.x`)
- **[maint]** `_exec_detached()` : log masqué simplifié, `HOME.name` pour portabilité
- **[maint]** `global_auth` : path portabilité via `Path.home()` (suppression du path absolu `/home/g33ky`)

### v1.0.0 — Juillet 2026

- Pipeline 4 passes fonctionnel et stabilisé en production
- Callback Telegram opérationnel (`response.status` fix)
- `anu-tg` : wrapper shell Telegram
- `--detach` : fork `systemd-run --user` avec injection `--setenv` des credentials
- `--resume` : reprise pipeline complet depuis dernier checkpoint valide
- `--status` : listing 20 derniers runs
- Détection mode TEACHER par mot entier (`\b`), prioritaire

### v0.9 — Juillet 2026

- Officialisation prod, pipeline stabilisé
- Callback Telegram fixé

### v0.1 — Juin 2026

- Pipeline 4 passes initial (`engine.py`, stdlib only)
- Intégration Hermes via `execute_code`
- 7 archétypes, checkpoints JSON, scoring P2

---

## Mainteneur

**Pytheas Infrastructure** — Usage interne exclusif.
Architecture : **Claude (Anthropic)** via MCP GitHub.
Implémentation : **Hermes** (Stepfun 3.7 flash, profil dev) depuis pytheas.

---

## About

ANU Mind is a structured multi-pass reasoning engine for **Hermes Agent**. Triggered via the `anu` command, it improves answer quality on complex topics by applying a 4-pass pipeline: generation → audit → conditional correction → validation. Automatic Telegram callback at the end of each detached run.

---

## Stack

| Component | Version | Source |
|-----------|---------|--------|
| Python | 3.11+ | system |
| Hermes | latest | `/home/g33ky/.hermes` |
| Stdlib only | — | no external dependencies |

---

## Contributing

### Commit conventions

| Prefix | Usage |
|--------|-------|
| `feat:` | New feature |
| `fix:`  | Fix |
| `docs:` | Documentation |
| `chore:`| Maintenance |

---

## License

Internal use — All rights reserved.

<div align="center">
  <sub>Composant de l’écosystème <strong>Hermes</strong> — Pytheas Infrastructure 🌿</sub>
</div>


## Structure

TODO
