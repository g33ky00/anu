# ANU Mind

<div align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/deps-stdlib%20only-4caf50" alt="Stdlib only" />
  <img src="https://img.shields.io/badge/Hermes-Skill-purple" alt="Hermes Skill" />
  <img src="https://img.shields.io/badge/Status-ACTIF%20PROD-brightgreen" alt="Status" />
</div>

<br>

> **Moteur de raisonnement structuré multi-passes pour Hermes Agent.**<br>
> Déclenché via la commande `anu` ou le slash `/anu`, il implémente le pattern d'ingénierie "Reflexion" pour atténuer les hallucinations des LLMs. Le système applique un pipeline 4 passes : génération → audit asynchrone → remédiation (conditionnelle) → validation. L'intégration OS est assurée par le wrapper `anu-tg` avec exécution en *transient unit* systemd.

---

## 1. Principes d'Architecture

ANU n’est pas un modèle fondationnel, mais un **orchestrateur d'inférence structurée**. Il contraint le LLM sous-jacent (Stepfun 3.7 flash via Hermes) à s'évaluer lui-même avant de délivrer son output. Cette approche casse le flux auto-régressif classique en injectant des étapes de validation déterministes.

```text
 anu <topic>
        │
 [P1] ━━┿━━ Génération initiale (Injection du System Prompt par Archétype)
        │
 [P2] ━━┿━━ Audit Statique + Scoring Matriciel (5 dimensions, 0-10)
        │
 [P3] ━━┿━━ Correction ciblée (Bifurcation si moyenne < 7.0 OU dim < 5)
        │
 [P4] ━━┿━━ Synthèse finale & Compilation Markdown → livrable p4.md

```

---

## 2. Structure du Dépôt (Single Source of Truth)

```text
anu/
├── tool.py                    ← Point d’entrée prod (lié vers ~/.local/bin/anu)
├── scripts/
│   ├── engine.py              ← Moteur 4-passes statique (zéro dépendance externe)
│   └── patch_auth.py          ← Utilitaire de remédiation Auth Telegram
├── install/
│   ├── anu-tg.sh              ← Wrapper Bash (Injection Env & Routage TG)
│   └── install.sh             ← Déploiement idempotent (ln -snf)
├── references/                ← Documentation d'ingénierie et de conception
│   ├── modes.md               ← Spécifications des 7 archétypes
│   ├── stepfun-nous-backend.md
│   ├── nous-model-naming.md
│   ├── provider-backend.md
│   └── ns-documentation.md
├── templates/
│   └── checkpoint_v1.json     ← Schéma contractuel d'état (State Machine)
├── tests/
│   ├── test_anu_tool.py
│   └── test_engine_integration.py
├── backups/                   ← Snapshots pré-déploiement (engine.py)
├── tool/
│   ├── anu_tool.py            ← Hook Hermes historique
│   └── tool_definition.json   ← Registration du Skill dans l'Event Loop Hermes
├── docs/
│   └── manuel_utilisation_fr.md
├── SKILL.md                   ← Metadata Hermes
└── README.md

```

---

## 3. Déploiement & Intégration Système

L'installation s'appuie sur des liens symboliques pour garantir que le dépôt Git reste l'unique source de vérité. Le script d'installation garantit l'idempotence des chemins utilisateur.

```bash
# Provisionnement et sécurisation de l'environnement CLI
bash install/install.sh

# Topologie post-déploiement attendue :
# ~/.local/bin/anu    -> <repo>/tool.py
# ~/.local/bin/anu-tg -> <repo>/install/anu-tg.sh

```

---

## 4. Usage & Interface CLI

Le binaire est conçu pour fonctionner en mode synchrone (bloquant) ou asynchrone (détaché via systemd).

```bash
anu <topic>               # Cold start (détection auto de l'archétype)
anu <topic> --mode N      # Forçage de l'archétype métier (1-7)
anu <topic> --detach      # Exécution asynchrone + Callback Telegram IPC
anu --resume <run_id>     # Reprise sur échec (réhydrate le contexte)
anu --status              # Topologie des 20 derniers runs

```

### Exemples d'Invocation

```bash
anu "audit SSH hardening" --mode 5
anu "refactor parser.py" --mode 2
anu "architecture NAS backup" --mode 1 --detach
anu --resume 20260719_132400

```

---

## 5. Matrices des Archétypes (Modes)

Le routage heuristique sélectionne le `system_prompt` optimal si aucun flag `--mode` n'est explicitement fourni.

| Mode | Codename | Domaine de compétence | Triggers Heuristiques (Regex) |
| --- | --- | --- | --- |
| 1 | `ARCHITECT` | Architecture logicielle, topologie infra | `architecture, design, schema, stack` |
| 2 | `CODER` | Génération de code, refactoring, debug | `code, debug, script, refactor` *(Défaut)* |
| 3 | `TEACHER` | Vulgarisation technique, documentation | `explique, tutoriel, documentation` |
| 4 | `PROTOCOL` | Workflows, standardisation, specs | `procedure, spec, protocole, yaml` |
| 5 | `AUDITOR` | Hardening, analyse de risques, CVEs | `audit, securite, risque` |
| 6 | `WRITER` | Rédaction formelle, rapports hiérarchiques | `redige, article, rapport` |
| 7 | `RESEARCHER` | Benchmark, analyse comparative | `recherche, compare, benchmark` |

---

## 6. Moteur d'Audit P2 : Dimensions de Scoring

Si la moyenne globale chute sous **7.0/10** ou si une dimension critique (risques, factualité) obtient une note **< 5**, le moteur bifurque sur P3 (Remédiation) avant de compiler P4. Les poids sont stricts et le LLM doit justify chaque décimale.

| Dimension | Vecteur d'analyse | Seuil d'Alerte |
| --- | --- | --- |
| `factualite` | Exactitude, absence d'hallucinations techniques | < 5 (Critique) |
| `couverture` | Exhaustivité de la réponse face au prompt initial | < 5 |
| `coherence` | Linéarité logique, absence de contradictions internes | < 5 |
| `risques` | Identification des impacts collatéraux (sécu/prod) | < 5 (Critique) |
| `clarte` | Lisibilité, formatage Markdown, scannabilité | < 5 |

---

## 7. Asynchronisme & Observabilité (Mode Detach)

L'utilisation de `--detach` isole le processus de la session shell courante via `systemd-run`.

* **Process Isolation :** Création d'une *transient unit* (`systemd-run --user --unit=anu-run-<run_id>`). Retour main au shell en < 2s.
* **Environment Propagation :** Les variables critiques (`TELEGRAM_CHAT_ID`, `DBUS_SESSION_BUS_ADDRESS`, `HERMES_PROFILE`) sont poussées en RAM dans le contexte de l'unité.
* **Callback Routing :** Le livrable final (P4) est streamé via le broker Telegram. Les payloads massifs (> 4096 octets) sont automatiquement fragmentés.

### Structure des Artefacts de Run

```text
~/.hermes/profiles/<profile>/cron/output/anu/<run_id>/
├── p1.md / p1.json
├── p2.md / p2.json    ← Matrice de scoring
├── p3.md / p3.json    ← Instancié uniquement si P2 déclenche un trigger
├── p4.md / p4.json    ← Livrable consolidé
└── .manifest.json     ← Écriture atomique (.tmp + os.replace)

```

---

## 8. Posture de Sécurité & Résolution des Secrets

L'architecture ANU est conçue selon le principe du moindre privilège (Zero Trust local) :

* **Memory-Only Secrets :** Les tokens ne sont jamais passés en arguments CLI (`argv`) pour éviter la fuite dans `ps aux` ou le `.bash_history`.
* **Log Masking :** Le token Telegram est dynamiquement tronqué dans le logger (`abcd****...wxyz`).
* **Code Execution :** Aucune fonction dynamique de type `eval()`, `exec()` ou `subprocess` direct depuis le LLM.

**Hiérarchie de résolution des credentials :**

1. Environnement dynamique enfant (`TELEGRAM_BOT_TOKEN`) injecté par wrapper.
2. Profil courant (`~/.hermes/auth.json`).
3. Configuration système (`config.yaml`).

---

## 9. Changelog Technique

### v0.9.1 — Juillet 2026

* **[feat]** Implémentation du déploiement idempotent des symlinks système via `install.sh` (`mkdir -p` + `ln -snf`).
* **[feat]** Intégration du script de routage Telegram (`anu-tg.sh`) dans le contrôle de version.
* **[maint]** Migration vers un modèle de Single Source of Truth intégral (zéro modification manuelle dans `~/.local/bin/`).

### v0.9.0 — Juillet 2026

* Validation du moteur 4-passes statique.
* Ajout des hooks `systemd-run` (mode `--detach`).
* Création de la machine d'état (`--status`, `--resume`).

---
