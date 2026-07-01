---
name: anu-mind
description: Use when the user invokes ANU and asks for structured multi-pass reasoning on a topic. Runs a 4-pass think-tank (analyst, auditor, corrector, validator) with checkpoints and outputs in Markdown, Mermaid, JSON, or XML.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [think-tank, multi-pass, structured-output]
    category: research
    requires_toolsets: [file, web, session_search, memory, code_execution]
    config: []
---

# ANU Mind — Think-Tank Multi-Pass

## Overview
Chargé de traiter un sujet en 4 passes contrôlées avec persistance sur disque. Pas d'interface interactive, pas d'appel API en dur : Hermes exécute `engine.py` via `execute_code`, le skill dicte la séquence, les critères de passage et les formats de sortie.

## When to Use
- Utilisateur demande explicitement ANU sur un sujet.
- Besoin d'une réflexion structurée, pas d'une réponse directe.
- Absence de cronjob et de gateway dédiée pour ce workflow.
- Provider/model stable : si la session en cours présente une instabilité de décodage/language model, changer de modèle/provider avant de lancer ANU.

## Provider / Backend Integration
- `engine.py` réutilise la config Hermes (`~/.hermes/config.yaml`, `~/.hermes/auth.json`) et le provider actif.
- `llm_generate(model="auto", ...)` résout le modèle défini dans Hermes et appelle l’endpoint `/chat/completions`.
- Rafraîchissement automatique du token sur 401/403 via `auth.json`. Arrêt définitif si le refresh échoue.
- Le backend peut renvoyer la réponse utile dans `message.reasoning` ou `message.reasoning_details[*].text` quand `content` est `null`. Le moteur ANU extrait ce champ avant de livrer `p*.md`.
- Détails pratiques : voir `references/stepfun-nous-backend.md`.

## Provider / Backend Rules
- `engine.py` utilise le backend LLM configuré dans Hermes via `config.yaml` + `auth.json`.
- Le nom de modèle passé à `llm_generate()` doit rester générique, ex `auto`.
- Pour Nous/Nous Portal, le contrat dépend de l'entitlement du compte ; le suffixe n'est pas décoratif.
  Le run gratui accepte `stepfun/step-3.7-flash:free`. Si le compte est crédité, `stepfun/step-3.7-flash` fonctionne.
  Si tu reçois HTTP 404 "requires available credits", cela signifie que le compte est sur du paid sans crédit, donc il faut soit ajouter des crédits, soit repasser sur le plan free.
- Si `engine.py` retourne `[DRY-RUN ...]` ou `[LLM ERROR]` : ne pas livrer ce texte brut comme résultat ANU. Soit Hermes injecte la génération réelle, soit elle signale explicitement qu'aucun backend LLM n'est actif.
- Règle modèle Nous/Nous Portal : voir `references/nous-model-naming.md`.


## Procedure
1. Charger les modes archétypage : `skill_view("anu_mind", "references/modes.md")`.
2. Créer la session de travail : répertoire `~/.hermes/profiles/dev/cron/output/anu/<run_id>/` avec `run_id = <YYYYMMDD_HHMMSS>`.
3. Sélectionner l'archétype (voir Modes ci-dessous) et noter `mode_id`.
4. Exécuter la passe P1 via `execute_code` en appelant `engine.py --topic "<sujet>" --mode <mode_id> --pass p1 --run-id <run_id>`.
5. Vérifier le checkpoint `p1.json` dans le répertoire de run.
6. Exécuter la passe P2 (audit) avec les mêmes args + `--pass p2 --input p1.md`.
7. Si score P2 `< 7/10` sur dimensions critiques : exécuter P3 (correction) avec `--pass p3 --input p2.md`; sinon signaler que P3 est sautée.
8. Exécuter P4 (validation) avec `--pass p4 --input p3.md ou p2.md>`.
9. Livrer au minimum `pass4.md` et, si demandé, les formats machine `result.json` / `result.xml`.
10. Journaliser la session complète dans `~/.hermes/profiles/dev/logs/hermes_YYYY-MM-DD.log` au niveau `AUTONOMOUS`.

## Modes (Archétypage)
Les modes sont définis dans `references/modes.md` (injecté à la demande). Chaque mode fournit :
- `name`
- `temperature`
- `system_prompt_template`
- `max_output_tokens`
- `output_constraints`

Sélection : choisir le mode dont le rôle correspond le mieux au sujet. Si le sujet couvre plusieurs dimensions, privilégier le mode dont la contrainte de sortie est la plus forte (ex: PROTOCOL pour JSON/YAML, TEACHER pour tutoriel, AUDITOR pour risque, RESEARCHER pour faits vérifiés).

## Checkpoints
Schéma dans `templates/checkpoint_v1.json`. Chaque passe écrit un checkpoint JSON avec :
- `run_id`, `pass_id`, `mode_id`, `topic`
- `input_file`, `output_file`
- `metrics`: `tokens_in`, `tokens_out`, `wall_time_s`
- `status`: `completed`, `skipped`, `failed`
- `score` (pour P2): mapping dimensions `factualite`, `couverture`, `coherence`, `risques`, `clarte` sur 0-10

## Output Formats
- Markdown par défaut.
- Mermaid : entourer le diagramme par ```mermaid ... ```.
- JSON : objet valide, rien hors objet racine.
- XML : prologue `<?xml version="1.0" encoding="UTF-8"?>`, pas de DTD.
Ne jamais mélanger les formats dans un même fichier Livrable = `pass4.md` + `result.json` optionnel.

## Common Pitfalls
- Boucle infinie P2→P3 : plafond à 3 passes de correction maximum.
- Injection de contexte non nettoyé : toujours passer par `engine.py` (pas de prompt shell).
- Oublier le `run_id` horodaté => collisions de dossiers.
- Modes inadaptés : si l'archétype n'existe pas, fallback sur mode 2 (CODER).
- Exécution interactive interdite : `engine.py` ne contient aucun `input()`.
- Réponse vide apparente : vérifier `choices[0].message.reasoning` / `reasoning_details[*].text`, pas seulement `content`.

## Verification Checklist
- [ ] `run_id` présent et unique dans le chemin de checkpoint.
- [ ] `pass1.json` status = completed + `p1.md` non vide.
- [ ] `pass2.json` status = completed + dimensions scorées 0-10.
- [ ] Si `p3` exécuté : `p3.md` diffère de `p2.md` (sinon inutile).
- [ ] `pass4.json` status = completed + `pass4.md` conforme format demandé.
- [ ] Aucun secret/API key en clair dans les fichiers de run.
- [ ] Hermes log `AUTONOMOUS` écrit pour la session.
