# ANU Mind

> Moteur de raisonnement structuré multi-passes pour **Hermes Agent — v1.0.0 Prod-Ready**.
> Déclenché via la commande `anu`, il améliore la qualité des réponses sur des sujets complexes
> en appliquant un pipeline 4 passes : génération → audit → correction (conditionnelle) → validation.
> Callback automatique via Telegram à l'issue de chaque run détaché.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Stdlib only](https://img.shields.io/badge/deps-stdlib%20only-4caf50)]()
[![Hermes Skill](https://img.shields.io/badge/Hermes-Skill-purple)]()
[![Version](https://img.shields.io/badge/version-1.0.0-blue)]()
[![Status](https://img.shields.io/badge/Status-PROD-brightgreen)]()

---

## Principe

ANU n'est pas un modèle différent — c'est une **méthode d'utilisation structurée** du même LLM
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
├── tool.py                          ← Point d'entrée prod (symlink ~/.local/bin/anu)
├── install.sh                       ← Installe anu-tg dans ~/.local/bin
├── install/
│   └── anu-tg.sh                    ← Wrapper shell : anu + --detach + chat_id
├── scripts/
│   ├── engine.py                    ← Moteur 4 passes (stdlib only, ~550 lignes)
│   └── patch_auth.py                ← Utilitaire patch auth.json (maintenance)
├── references/
│   ├── architecture.md              ← Architecture technique détaillée
│   ├── modes.md                     ← Spécifications 7 archétypes
│   ├── anu-slash-command.md         ← Référence commande /anu
│   ├── stepfun-nous-backend.md      ← Quirks réponse Stepfun/Nous
│   ├── provider-backend.md          ← Règles provider/backend
│   ├── nous-model-naming.md         ← Nommage modèles Nous
│   ├── ns-documentation.md          ← Documentation NS
│   ├── run_passes-return-none-diagnosis.md
│   └── deployment-mode-v1.0.md     ← Addendum certification V1.0 et limites CLI `anu`
├── docs/
│   └── manuel_utilisation_fr.md    ← Manuel utilisateur complet (FR)
├── templates/
│   └── checkpoint_v1.json          ← Schéma checkpoint par passe
├── backups/                         ← Snapshots horodatés engine.py
├── tests/                           ← Tests unitaires et intégration
├── SKILL.md                         ← Définition skill Hermes
└── README.md
```

> `tool/` contient le squelette architecte Claude (référence).
> `tool.py` à la racine est l'implémentation réelle en production.

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
anu "<topic>" --context           # injecte les 5 derniers messages de la session
anu "<topic>" --context N         # injecte les N derniers messages de la session
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
anu "analyse ce contexte" --context
anu "approfondis ce point" --context 10
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

---

## Pipeline détaillé

### Règles d'exécution

| Passe | Rôle | Condition | Timeout |
|---|---|---|---|
| P1 | Génération initiale | Toujours | 600s |
| P2 | Audit + scoring 5 dimensions | Toujours | 600s |
| P3 | Correction ciblée | `mean < 7.0` OU dimension `< 5` | **600s (volontaire)** |
| P4 | Validation finale | Toujours | 600s |

Le timeout P3 à 600 secondes est intentionnel — cette phase nécessite le temps pour produire
une correction de qualité sur des sujets complexes.

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

## Option `--context` — Injection de contexte session

| Syntaxe | Comportement |
|---|---|
| *(absent)* | Cold start — aucun contexte injecté |
| `--context` | Injecte les 5 derniers messages de la session active |
| `--context N` | Injecte les N derniers messages de la session active |

Le contexte est préfixé au topic avant injection dans P1.
Utile pour approfondir ou étendre une réflexion en cours de session Hermes.

---

## Mode `--detach` (arrière-plan)

- Fork via `systemd-run --user --unit=anu-run-<run_id>`
- Retour shell < 2 s garanti
- Callback Telegram automatique à la fin (succès ou échec)
- Environnement injecté : `XDG_RUNTIME_DIR`, `DBUS_SESSION_BUS_ADDRESS`, `HERMES_HOME`,
  `PROFILE`, `HOME`, `USER`, `PATH`, `TELEGRAM_CHAT_ID`

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

`install/anu-tg.sh` est un raccourci opiné pour les invocations Telegram courantes :

```bash
# Ce que fait anu-tg :
export TELEGRAM_CHAT_ID="${2:-$DEFAULT_CHAT_ID}"   # -5380549950 par défaut
anu "$1" --mode 3 --detach                          # mode TEACHER, arrière-plan
```

`DEFAULT_CHAT_ID` est défini dans `install/anu-tg.sh` — modifier directement si nécessaire.

---

## Variables d'environnement

| Variable | Défaut | Rôle |
|---|---|---|
| `HERMES_PROFILE` | `dev` | Profile Hermes actif |
| `PROFILE` | `dev` | Alias HERMES_PROFILE (compatibilité) |
| `HERMES_HOME` | `~/.hermes/profiles/<profile>` | Racine Hermes du profil |
| `TELEGRAM_BOT_TOKEN` | — | Override token (prioritaire sur auth.json) |
| `TELEGRAM_CHAT_ID` | — | Override chat_id destination |

**Lecture des credentials Telegram (priorité décroissante) :**

1. Env vars `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`
2. `~/.hermes/auth.json` → `providers.telegram` (`access_token`, `bot_token` ou `token`)
3. `~/.hermes/config.yaml` → section `telegram:`

---

## Backend LLM

ANU réutilise intégralement la configuration Hermes — aucune clé API ni endpoint codé en dur.

```
~/.hermes/config.yaml    ← model.provider + model.default + base_url
~/.hermes/auth.json      ← access_token + refresh_token + inference_base_url
```

- Modèle résolu : `_resolved_model("auto")` → `model.default` → `stepfun/step-3.7-flash:free`
- Endpoint : `_resolved_base_url()` → `config.base_url` sinon `auth.inference_base_url`
- Refresh token OAuth2 automatique sur 401/403
- Extraction réponse Stepfun : `content` → `reasoning` → `reasoning_details[*].text`

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
- Inputs : `topic`, `--mode`, `--context` uniquement — pas d'`eval()`, `exec()`, ni `subprocess` avec input utilisateur

---

## Limitations connues

- Erreur bash `impossible de régler le groupe de processus du terminal` : attendue hors terminal de contrôle, sans impact fonctionnel.
- `auth.json` absent/corrompu : callbacks Telegram désactivés, tracé `credentials_missing`.
- `PROFILE` absent depuis shell brut : repli automatique sur `dev`.
- `TELEGRAM_CHAT_ID` manquant en env → tracé `telegram_credentials_diag`, pas d'erreur fatale.
- Voir aussi `references/deployment-mode-v1.0.md` pour les limites opérationnelles certifiées de la CLI `anu` et les règles d'appel direct `engine.py` en batch.

---

## Certification V1.0 — Recette N4 (2026-07-22)

- Campagne retenue : **35 runs isolés**, 5 profils autorisés, 7 modes couverts.
- Taux de succès : **94.2 %** en cold start multi-profils.
- Interprétation des échecs : ils valident la robustesse du contrat P2, pas un défaut d'orchestration.
- Document source : `references/deployment-mode-v1.0.md`

---

## Changelog

### v1.0.0 — Juillet 2026 *(prod-ready)*

- **[certification]** Recette N4 validée : 35 runs, 5 profils, 7 modes.
- **[docs]** Addendum `references/deployment-mode-v1.0.md` : voie d'exécution retenue, limitation CLI `anu`, roadmap V1.1.
- **[maint]** README rebasé sur dépôt distant, métadonnées V1.0.0 ajoutées.

### v0.9.1 — Juillet 2026

- **[prod]** Pipeline 4 passes fonctionnel et stabilisé en production
- **[prod]** Callback Telegram opérationnel (`response.status` fix)
- **[feat]** `--context [N]` : injection de contexte session (défaut 5 messages, cold start si absent)
- **[feat]** `anu-tg` : wrapper shell Telegram (mode TEACHER, detach, chat_id configurable)
- **[feat]** `--detach` : fork `systemd-run --user` avec injection complète d'environnement
- **[feat]** `--resume` : reprise pipeline complet depuis dernier checkpoint valide
- **[feat]** `--status` : listing 20 derniers runs avec score P2
- **[fix]** Timeout P3 à 600s (volontaire — phase de correction longue)
- **[fix]** `DEFAULT_RUN_ROOT` / `ENGINE_DEFAULT` respectent `HERMES_PROFILE` env var
- **[fix]** Token Telegram masqué dans tous les logs
- **[fix]** Manifest écriture atomique `.tmp` + `os.replace`
- **[fix]** Diagnostic credentials Telegram précis (`credentials_diag` log)
- **[maint]** `scripts/patch_auth.py` : utilitaire maintenance auth.json
- **[docs]** `docs/manuel_utilisation_fr.md` : manuel complet FR
- **[docs]** `references/architecture.md` : architecture technique détaillée

### v0.1 — Juin 2026 *(prototype)*

- Pipeline 4 passes initial (`engine.py`, stdlib only)
- Intégration Hermes via `execute_code`
- 7 archétypes, checkpoints JSON, scoring P2

---

## Mainteneur

**Pytheas Infrastructure** — Usage interne exclusif.
Architecture : **Claude (Anthropic)** via MCP GitHub.
Implémentation : **Hermes** (Stepfun 3.7 flash, profil dev) depuis pytheas.

<div align="center">
  <sub>Composant de l'écosystème <strong>Hermes</strong> — Pytheas Infrastructure 🌿</sub>
</div>
