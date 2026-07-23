# ANU Mind — Mode de déploiement certifié V1.0
> Addendum de déploiement. Ne remplace pas `SKILL.md`.
## Statut V1.0
- Certification Prod-Ready — recette N4, 2026-07-22.
- 35 runs, 5 profils, 7 modes — 94.2 % de succès.
- Les échecs résiduels valident le patch N5, pas un défaut d'orchestration.
## Voie d'exécution retenue
- Point d'entrée opérationnel certifié : `scripts/engine.py`
- Principe : run_id unique par test.
- Pattern d'appel validé : `engine.py --run-id <YYYYMMDD_HHMMSS>_<TEST_ID>`.
- Répertoire d'exécution : `<HERMES_HOME>/profiles/<profile>/cron/output/anu/<run_id>/`
## Limitation CLI `anu`
- Pas de `--run-id` dans le wrapper `anu`.
- Règle V1.0 : ne pas utiliser `anu` pour des runs parallèles ou batchs techniques.
## Roadmap V1.1
- Boucle P2 : retry JSONDecodeError × 2 avant RuntimeError définitif.
