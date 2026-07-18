---
name: anu-mind
description: |
  Pipeline de raisonnement structuré 4 passes (génération, audit, correction, validation).
  Déclenché exclusivement via la slash command /anu.
  Améliore la qualité et pertinence des réponses Hermes sur des sujets complexes.
version: 2.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [think-tank, multi-pass, structured-output, slash-command]
    category: research
    requires_toolsets: [file, code_execution, memory, session_search]
    config: []
---

# ANU Mind — Think-Tank Multi-Pass

## Point d'entrée

**`/anu` est le seul point d'entrée autorisé.**  
Ne jamais appeler `scripts/engine.py` directement depuis une session Hermes.  
Voir `tool/tool_definition.json` pour la déclaration du tool et `references/anu-slash-command.md` pour la référence complète.

## When to Use

- Utilisateur invoque explicitement `/anu <topic>`
- Sujet complexe nécessitant raisonnement structuré, pas une réponse directe
- Besoin de traçabilité (checkpoints JSON, score d'audit, log AUTONOMOUS)
- Provider/model stable : si instabilité de décodage, changer de modèle avant de lancer ANU

## Procedure

1. Vérifier que `engine.py` est accessible via `check_prerequisites()`
2. Détecter le mode archétype si non spécifié (`detect_mode(topic)`)
3. Générer `run_id = YYYYMMDD_HHMMSS`
4. Exécuter `tool/anu_tool.py` via `execute_code` ou invocation directe
5. Livrer `p4.md` comme réponse principale avec résumé (score P2, durée, run_id)
6. Logger la session en `AUTONOMOUS`

## Modes (Archétypes)

| ID | Nom | Domaine principal |
|---|---|---|
| 1 | ARCHITECT | Architecture, infrastructure, design système |
| 2 | CODER | Code, debug, scripts (défaut) |
| 3 | TEACHER | Documentation, tutoriels, explications |
| 4 | PROTOCOL | Procédures, specs, workflows |
| 5 | AUDITOR | Sécurité, audit, risques |
| 6 | WRITER | Rédaction, rapports, synthèses |
| 7 | RESEARCHER | Recherche, comparaisons, faits |

Détail complet : `references/modes.md`

## Provider / Backend

- `engine.py` réutilise la config Hermes (`config.yaml` + `auth.json`)
- `llm_generate(model="auto")` — ne jamais hardcoder le slug modèle
- Stepfun 3.7 flash : réponse utile dans `message.reasoning` ou `reasoning_details[*].text` quand `content` est null
- Détails : `references/stepfun-nous-backend.md`

## Checkpoints

Schéma : `templates/checkpoint_v1.json`

```
~/.hermes/profiles/<profile>/cron/output/anu/<run_id>/
├── p1.md / p1.json
├── p2.md / p2.json   # score: {factualite, couverture, coherence, risques, clarte}
├── p3.md / p3.json   # si score P2 < 7.0
├── p4.md / p4.json   # livrable principal
└── .manifest.json
```

## Common Pitfalls

- Appeler `engine.py` directement → interdit, passer par `/anu`
- Boucle P3 infinie : plafond 3 corrections maximum
- Score P2 nul (0.0) si `p2.json` absent ou malformé : ne pas déclencher P3 sur cette base
- Réponse vide : vérifier `choices[0].message.reasoning` avant `content`
- `run_id` manquant → collisions de dossiers

## Verification Checklist

- [ ] `check_prerequisites()` → aucune erreur
- [ ] `run_id` présent et unique
- [ ] `p1.json` status = completed + `p1.md` non vide
- [ ] `p2.json` status = completed + dimensions scorées
- [ ] Si P3 : `p3.md` diffère de `p2.md`
- [ ] `p4.json` status = completed + `p4.md` conforme format
- [ ] Aucun secret en clair dans les fichiers de run
- [ ] Log AUTONOMOUS écrit
