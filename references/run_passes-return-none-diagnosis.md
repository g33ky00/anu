# Diagnostic précis — `run_passes()` retourne `None`

## 1. Structure fonctionnelle concernée

Composant : `scripts/engine.py`
Fonction : `run_passes(run_dir: Path, args: argparse.Namespace) -> Dict[str, Any]`

Signature promet un dictionnaire de résultat.
Réalité observée : retourne `None` à tous les appels testés, malgré l’écriture réussie des fichiers de run.

## 2. Structure de fichiers produite

Répertoire de run : `~/.hermes/profiles/dev/cron/output/anu/<run_id>/`

Fichiers effectivement écrits par `run_passes()` :

- `p1.json` — checkpoint passe 1
- `p1.md` — sortie Markdown passe 1
- `p2.json` (si p2 exécutée)
- `p2.md` (si p2 exécutée)
- `p3.json` / `p3.md` (si correction requise)
- `p4.json` / `p4.md` (validation finale)
- `.manifest.json` (métadonnées de run)

Schéma JSON attendu par passe (`templates/checkpoint_v1.json`) :

```json
{
  "$schema": "checkpoint_v1",
  "run_id": "20260101_120000",
  "pass_id": "p1",
  "mode_id": 2,
  "topic": "Sujet ANU",
  "input_file": null,
  "output_file": "p1.md",
  "metrics": {
    "tokens_in": 0,
    "tokens_out": 0,
    "wall_time_s": 0.0
  },
  "status": "completed",
  "score": null,
  "errors": []
}
```

## 3. Méthodes impliquées dans le flux

| Méthode | Rôle | Retour |
|---|---|---|
| `run_passes()` | Workflow principal | **`None` observé** ; signature `-> Dict[str, Any]` |
| `llm_generate()` | Appel LLM | `str` (texte extrait ou `[LLM ERROR]`) |
| `_llm_backend()` | Orchestration HTTP + auth | `str` |
| `_resolved_model()` | Résolution slug modèle | `str` |
| `_resolved_base_url()` | Construction endpoint | `str` |
| `_load_config()` | Lecture `config.yaml` | `Dict[str, Any]` |
| `_load_auth()` | Lecture `auth.json` | `Dict[str, Any]` |
| `_refresh_access_token()` | Rafraîchissement OAuth | `Dict[str, Any]` |
| `_http_json()` | Requête HTTP JSON | `Dict[str, Any]` |

## 4. Logigramme de fonctionnement de `run_passes()`

```
ENTRÉE run_passes(run_dir, args)
│
├── Validation mode_id ∈ MODES
│
├── Validation start_pass ∈ ALLOWED_TRANSITIONS ou == "p1"
│
├── Si start_pass != "p1" :
│   └── Vérification existence checkpoints précédents
│
├── Cible de départ = start_pass
│   └── Si start_pass == "p4" et p2.json existe :
│       └── Calcul score moyen
│           ├── Si score >= seuil et pas de critical_low → cible = "p4"
│           └── Sinon → cible = "p3"
│
├── BOUCLE while True :
│   ├── Sélection mode = MODES[mode_id]
│   ├── Construction checkpoint ck (status="running")
│   ├── Détermination entrée utilisateur
│   │   ├── p2/p3/p4 : lecture fichier Markdown précédent
│   │   └── p1 : topic brut
│   ├── Appel llm_generate(model="auto", ...)
│   ├── Écriture p<pass>.md
│   ├── Écriture p<pass>.json (checkpoint)
│   │   └── Si p2 : calcul dimensions, écriture score
│   ├── Si p4 :
│   │   ├── Écriture p4.json
│   │   └── Sortie de boucle ?
│   └── Transition vers passe suivante
│
└── RETOUR ?
```

## 5. Diagnostic précis du défaut de retour

### Observation empirique

- `p1.json`, `p1.md`, `.manifest.json` sont bien écrits sur disque.
- Checkpoint contient bien `"status": "completed"`.
- `run_passes()` retourne `None` en Python.

### Conclusion

La fonction exécute correctement son flux d’écriture, mais ne construit pas et ne retourne pas d’objet de résultat agrégé.

### Causes racines probables (non exhaustives)

1. **Absence de variable de retour** : la fonction écrit sur disque via des effets de bord mais n’accumule pas les métriques dans une variable `result` qu’elle retournerait en fin de flux.

2. **Sortie de boucle sans `return`** : la boucle `while True` contient un `break` ou une condition de sortie qui ne précède pas d’instruction `return result`.

3. **Chemin d’erreur sans remontée** : en cas d’exception attrapée, la fonction peut écrire un checkpoint d’erreur mais ne pas propager ou retourner l’erreur à l’appelant.

4. **Hypothèse de contrat** : le design semble été créé pour un appel externe via CLI (`engine.py --pass p1 --run-id ...`) où le résultat est consommé par lecture de fichier, et non par retour de fonction. L’appel via `execute_code` expose alors ce défaut d’instrumentation.

### Diagnostic recommandé

1. Ajouter `result = {}` en début de `run_passes()`.
2. Mettre à jour `result` à chaque événement :
   - `result["status"] = ck["status"]`
   - `result["last_pass"] = target_pass`
   - `result["output_file"] = ck["output_file"]`
   - `result["errors"] = ck["errors"]
   - `result["metrics"] = ck["metrics"]
3. Retourner `result` en toute fin de fonction, après la boucle.
4. Ajouter un log `AUTONOMOUS` avec le contenu de `result` pour traçabilité.

### Impact du défaut

- Aucun impact sur la production des fichiers de run.
- Impact sur l’appel programmatique depuis Hermes : impossibilité de vérifier le résultat sans lecture disque.
- Impact sur l’automatisation : fragilité, dépendance à la présence fichiers.

### Rollback

Aucune modification nécessaire : le défaut est une absence, pas une corruption. La correction est purement additive.
