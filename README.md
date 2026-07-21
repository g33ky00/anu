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
