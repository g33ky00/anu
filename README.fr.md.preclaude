# Manuel d'utilisation — `anu`

## 1. Vue d'ensemble
`anu` est un moteur asynchrone de traitement en 4 passes : Archetype, Structuring, Drafting, Finalization. Il expose une CLI dédiée via le point d'entrée partagé OS :
- `~/.local/bin/anu` → `/home/g33ky/.hermes/skills/autonomous-ai-agents/anu-mind/tool.py`

## 2. Syntaxe exacte
```bash
anu <topic> [--mode N] [--resume RUN_ID] [--status] [--detach]
```
| Argument | Rôle |
|---|---|
| `<topic>` | Texte libre du sujet |
| `--mode N` | Archétype d'exécution 1-7 |
| `--resume RUN_ID` | Reprise de run interrompu |
| `--status` | Liste des runs en cours |
| `--detach` | Fork arrière-plan + callback Telegram |

## 3. Modes
| Mode | Nom | Usage |
|---|---|---|
| 1 | ARCHITECT | Conception, structures, schémas |
| 2 | CODER | Scripts, refactor, implémentation |
| 3 | TEACHER | Explication pédagogique |
| 4 | PROTOCOL | Procédures, runbooks |
| 5 | AUDITOR | Audit, conformité, risques |
| 6 | WRITER | Synthèse, contenu, rapports |
| 7 | RESEARCHER | Recherche, sourcing, benchmark |

## 4. Synchrone vs asynchrone
### Avant-plan
- Commande sans `--detach` : exécution synchrone dans le worker foreground.
- Limite pratique : ~180 s.

### Arrière-plan
- `--detach` : fork via `systemd-run --user --unit="anu-run-${run_id}"`.
- Retour frontend garanti < 2 s.
- Callback Telegram automatique à la fin du run.
- Injection d’environnement assurée : `XDG_RUNTIME_DIR`, `DBUS_SESSION_BUS_ADDRESS`, `HERMES_HOME`, `PROFILE`, `HOME`, `USER`.

## 5. Stockage et profil par défaut
- Artefacts par run :
  ```
  ~/.hermes/profiles/<profil>/cron/output/anu/<run_id>/
  ├── p1.md, p1.json
  ├── p2.md, p2.json
  ├── p3.md, p3.json
  ├── p4.md, p4.json
  └── .manifest.json
  ```
- Si `PROFILE` est absent lors d’un appel manuel depuis un shell brut, le repli est **`dev`**.
- `HERMES_HOME` absent → repli sur `/home/g33ky/.hermes/profiles/dev`.

## 6. Pipeline interne
### Règle vérifiée
- **P1** : cadrage et extraction → toujours exécutée.
- **P2** : audit et notation → toujours exécutée.
- **P3** : correction conditionnelle → **uniquement si** `mean < 7.0` OU une des dimensions `factualite`, `couverture`, `coherence`, `risques`, `clarte` est `< 5`.
- **P4** : validation finale → toujours exécutée.

### Manifest
- Écriture atomique garantie : `.tmp` puis `os.replace`.
- Chemins absolus dynamiques basés sur `HERMES_HOME`.

## 7. Callback Telegram
- Si callback activé, le livrable est **fractionné** en chunks de `<= 4096` caractères.
- Chaque chunk est un message indépendant.
- Succès : `[ANU | <MODE> | Run <run_id> | Score P2: <mean>/10]` + contenu de `p4.md`.
- Échec : `🚨 [ANU - ERREUR FATALE] Echec sur la passe ... / Reprise possible via : /anu --resume <run_id>`.

## 8. Logging
Fichier :
```
~/.hermes/profiles/dev/logs/hermes_YYYY-MM-DD.log
```
Événements tracés :
- run_start_detach
- exécution P<N> avec statut et métriques
- telegram_push_start chat_id=...
- telegram_push_failed reason=...
- erreurs d’écriture manifest

## 9. Commandes usuelles
```bash
anu "Sujet" --mode 2
anu "Sujet" --mode 2 --detach
anu --status
anu --resume 20260719_140011_verif
tail -n 10 ~/.hermes/profiles/dev/cron/output/anu/<run_id>/.manifest.json
```

## 10. Limitations et erreurs connues
- Erreur bash `impossible de régler le groupe de processus du terminal` : systématique hors terminal de contrôle, sans impact fonctionnel.
- `sudo` en environnement non interactif : peut échouer sans NOPASSWD configuré.
- Si `auth.json` manque/corrompu, les callbacks Telegram sont désactivés et tracés comme `credentials_missing`.

## 11. Sécurité
- Credentials Telegram lus dans `/home/g33ky/.hermes/auth.json` ou variables d’environnement.
- Aucun secret exposé dans les callbacks ou logs d’exécution standard.
