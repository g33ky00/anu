# Architecture ANU — Cartographie explicative + Manuel de fonctionnement

## 1. Vue d’ensemble

ANU Mind est un moteur de raisonnement structuré multi-passes, implémenté comme un skill Hermes autonome. Il n’a ni gateway dédiée, ni cronjob attaché ; il est exécuté à la demande par Hermes via `execute_code` en appelant `scripts/engine.py`.

**Principe fondamental** : aucun composant ne contient de dépendance fournisseur codée en dur, aucune référence à Google/Gemini, aucun secret en clair dans le code ou les artefacts produits. Toute la stack LLM provient de Hermes : `~/.hermes/config.yaml` + `~/.hermes/auth.json`.

---

## 2. Structure de fichiers

```
anu_mind/
├── scripts/
│   └── engine.py                          # Moteur principal
├── references/
│   ├── modes.md                           # Spécifications 7 archétypes
│   ├── provider-backend.md                # Règles provider/backend
│   ├── stepfun-nous-backend.md            # Quirks réponse Stepfun/Nous
│   ├── nous-model-naming.md               # Règles nommage modèles Nous
│   ├── run_passes-return-none-diagnosis.md # Diagnostic défaut retour
│   └── ns-documentation.md                # Documentation NS
├── templates/
│   └── checkpoint_v1.json                 # Schéma checkpoint
├── SKILL.md                               # Définition skill
└── backups/
    └── engine_YYYYMMDD_HHMMSS.bak         # Snapshots horodatés
```

### 2.1 `scripts/engine.py`

Fichier central. 544 lignes. Dépendances : Python stdlib uniquement (`json`, `urllib`, `re`, `time`, `datetime`, `argparse`, `pathlib`).

**Rôles par section :**

| Section | Fonctions | Rôle |
|---|---|---|
| AUTH/CONFIG | `_load_config()`, `_load_auth()`, `_mask_token()` | Lecture config/auth Hermes, masquage secrets |
| TOKEN MGMT | `_refresh_access_token()` | Rafraîchissement OAuth2 sur 401/403 |
| HTTP | `_http_json()` | Client POST JSON avec timeout |
| LLM BACKEND | `_resolved_model()`, `_resolved_base_url()`, `_llm_backend()`, `llm_generate()` | Résolution modèle, appel LLM, extraction réponse |
| WORKFLOW | `run_passes()`, `write_checkpoint_atomic()`, `log_autonomous()` | Orchestration 4 passes, écriture checkpoints |
| CLI | `main()` | Point d’entrée argparse |
| UTILS | `scrub_secrets()`, `prompt_hash()`, `compute_score()`, `make_run_dir()` | Nettoyage, hashing, scoring, création répertoire |

### 2.2 `references/modes.md`

Déclare les 7 archétypes ANU. Chaque entrée contient :
- `id` : 1 à 7
- `nom` : ARCHITECT, CODER, TEACHER, PROTOCOL, AUDITOR, WRITER, RESEARCHER
- `temperature` : 0.0 à 0.8
- `max_output_tokens` : 1000 ou 8192
- `axes de sortie` : formats autorisés

Le mode 2 (CODER) est le fallback si l’archétype demandé n’existe pas.

### 2.3 `templates/checkpoint_v1.json`

Schéma JSON de checkpoint par passe :

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

`score` est rempli uniquement pour P2 (audit). Les dimensions sont : `factualite`, `couverture`, `coherence`, `risques`, `clarte` (0-10).

### 2.4 Documentation de référence

| Document | Rôle |
|---|---|
| `provider-backend.md` | Règles générales provider/backend |
| `stepfun-nous-backend.md` | Endpoint, auth, quirk réponse Stepfun |
| `nous-model-naming.md` | Règles de nommage de modèles pour Nous |
| `ns-documentation.md` | Documentation NS complète |
| `run_passes-return-none-diagnosis.md` | Diagnostic défaut retour |

---

## 3. Architecture logicielle

### 3.1 Stack technique

- **Langage** : Python 3.13
- **Runtime** : stdlib uniquement, pas de dépendances externes
- **Auth** : héritée de Hermes (`~/.hermes/auth.json`)
- **Config** : héritée de Hermes (`~/.hermes/config.yaml`)
- **Sortie** : Markdown + JSON checkpoint
- **Exécution** : via Hermes `execute_code` ou CLI directe

### 3.2 Flux d’exécution global

```
UTILISATEUR
    │
    ▼
HERMES (execute_code)
    │
    ├── import engine.py
    ├── make_run_dir() → run_id
    ├── run_passes(run_dir, args)
    │       │
    │       ├── Validation mode_id
    │       ├── Détermination start_pass (auto pour p1)
    │       ├── BOUCLE while True :
    │       │   ├── Sélection mode archétype
    │       │   ├── Résolution entrée (topic ou fichier précédent)
    │       │   ├── llm_generate(model="auto", ...)
    │       │   │       │
    │       │   │       ├── _resolved_model("auto")
    │       │   │       │   └── config.yaml → model.default : stepfun/step-3.7-flash:free
    │       │   │       ├── _resolved_base_url()
    │       │   │       │   └── auth.json → inference_base_url : https://inference-api.nousresearch.com/v1
    │       │   │       ├── _load_auth() → access_token
    │       │   │       ├── _refresh_access_token() si expiré
    │       │   │       ├── _http_json(POST /chat/completions)
    │       │   │       └── Extraction : content → reasoning → reasoning_details[*].text
    │       │   │
    │       │   ├── Écriture p<pass>.md
    │       │   ├── Écriture p<pass>.json (checkpoint)
    │       │   ├── Si p2 : calcul score dimensions
    │       │   ├── Transition p1→p2→p3→p4
    │       │   └── break après p4
    │       │
    │       └── RETURN result (dict)
    │
    └── Livraison résultat à l'utilisateur
```

---

## 4. Méthodes de déclaration des composants

### 4.1 `_load_config()`

**Déclaration** : parseur YAML manuel, pas de dépendance PyYAML.

**Entrée** : `~/.hermes/config.yaml`

**Sortie** : `Dict[str, Any]` avec clés :
- `provider` : provider actif (ex: `nous`)
- `default_model` : slug modèle par défaut (ex: `stepfun/step-3.7-flash:free`)
- `base_url` : URL base optionnelle
- `api_key` : clé API optionnelle

**Méthode** : lecture ligne par ligne, détection bloc `model:`, extraction clés `provider`, `default`, `base_url`, `api_key`. Gestion indentations YAML variables.

**Contrat** : retourne un dict vide si fichier absent ou invalide.

### 4.2 `_load_auth()`

**Déclaration** : parseur JSON.

**Entrée** : `~/.hermes/auth.json`

**Sortie** : `Dict[str, Any]` normalisé :
- `active_provider` : provider actif
- `access_token` : token d’accès
- `refresh_token` : token de rafraîchissement
- `client_id` : ID client OAuth
- `token_type` : `Bearer`
- `portal_base_url` : URL portail Nous
- `inference_base_url` : URL endpoint inférence
- `agent_key` : clé agent optionnelle

**Méthode** : lecture JSON → extraction `providers.<active_provider>` ou `providers.nous` → cache global `_AUTH_CACHE`.

### 4.3 `_resolved_model()`

**Déclaration** : resolveur de slug modèle.

**Signature** : `_resolved_model(model: str) -> str`

**Comportement** :
- `model != "auto"` → retour direct
- `model == "auto"` → lecture `config.yaml → model.default`, fallback `stepfun/step-3.7-flash:free`

**Contrat critique** : ne tronque pas le suffixe `:free`. Le suffixe est autorisé et nécessaire pour le plan gratuit Nous.

### 4.4 `_resolved_base_url()`

**Déclaration** : constructeur d’URL endpoint.

**Signature** : `_resolved_base_url() -> str`

**Comportement** :
- Si `config.yaml → base_url` présent → utilisation directe + `/chat/completions`
- Sinon → `auth.json → inference_base_url` + `/chat/completions`

**Sortie** : URL complète vers endpoint `/chat/completions`.

### 4.5 `_refresh_access_token()`

**Déclaration** : client OAuth2 refresh.

**Signature** : `_refresh_access_token() -> Dict[str, Any]`

**Entrée** : `auth.json` (`refresh_token`, `client_id`, `portal_base_url`)

**Sortie** :
- `{"ok": True, "access_token": ..., "expires_at": ..., ...}`
- `{"ok": False, "error": "..."}`

**Méthode** : `POST {portal_base_url}/oauth2/token` avec formulaire URL-encodé.

### 4.6 `_http_json()`

**Déclaration** : client HTTP générique.

**Signature** : `_http_json(url, payload, headers, timeout=60) -> Dict[str, Any]`

**Comportement** :
- POST JSON
- Succès → parse JSON body
- HTTPError → retour `{"__http_error__": True, "status": code, "reason": ..., "body": ...}`

### 4.7 `_llm_backend()`

**Déclaration** : orchestrateur LLM.

**Signature** : `_llm_backend(model, user_prompt, system_instruction, max_tokens, temperature) -> str`

**Comportement** :
1. Lecture auth + résolution modèle + URL
2. Construction payload OpenAI-compatible
3. Vérification expiration token → refresh si nécessaire
4. Appel `_http_json()`
5. Si 401/403 → refresh + nouvel appel
6. Extraction texte depuis `choices[0].message`
7. Retour texte ou `[LLM ERROR]`

### 4.8 `llm_generate()`

**Déclaration** : interface publique.

**Signature** : `llm_generate(model, user_prompt, system_instruction, max_tokens, temperature) -> str`

**Comportement** : délègue à `_llm_backend()`.

**Convention d’appel** : `model="auto"` pour résolution depuis config.

### 4.9 `run_passes()`

**Déclaration** : workflow principal.

**Signature** : `run_passes(run_dir: Path, args: argparse.Namespace) -> Dict[str, Any]`

**Structure interne** :

```
Début
├── Initialisation result = {"status": "pending", ...}
├── Validation mode_id ∈ MODES
├── Validation start_pass
├── Si start_pass != "p1" : vérification checkpoints précédents
├── Détermination cible départ (p1/p2/p3/p4 auto)
│
├── BOUCLE while True :
│   ├── Sélection mode = MODES[mode_id]
│   ├── Construction ck (status="running")
│   ├── Résolution entrée
│   ├── llm_generate(model="auto", ...)
│   ├── text = scrub_secrets(raw)
│   ├── Écriture p<pass>.md
│   ├── Calcul métriques (tokens_in, tokens_out, wall_time_s)
│   ├── Si p2 : calcul score dimensions
│   │   ├── mean >= seuil et pas critical_low → status="completed"
│   │   ├── hash identique → status="failed"
│   │   └── sinon → status="needs_correction"
│   ├── Sinon → status="completed"
│   ├── Mise à jour result depuis ck
│   ├── Écriture checkpoint atomique
│   ├── Log AUTONOMOUS
│   ├── Si needs_correction et max tentatives atteint → break
│   ├── Si needs_correction → target_pass="p3", continue
│   ├── Si p3 → target_pass="p4", continue
│   └── Sinon → break
│
├── Construction manifest (.manifest.json)
├── result["status"] = completed si pending
└── RETURN result
```

**Retour** : dictionnaire avec clés :
- `status` : `completed`, `failed`, `needs_correction`
- `last_pass` : `p1`, `p2`, `p3` ou `p4`
- `output_file` : chemin Markdown de la dernière passe
- `errors` : liste d’erreurs
- `metrics` : `tokens_in`, `tokens_out`, `wall_time_s`

### 4.10 `write_checkpoint_atomic()`

**Déclaration** : écriture atomique JSON.

**Comportement** : écriture fichier via écriture temporaire + rename pour éviter corruption.

### 4.11 `log_autonomous()`

**Déclaration** : journalisation niveau AUTONOMOUS.

**Comportement** : écrit dans `~/.hermes/profiles/dev/logs/hermes_YYYY-MM-DD.log`.

---

## 5. Méthodes d’appel

### 5.1 Appel depuis Hermes

```python
from pathlib import Path
from importlib.util import spec_from_file_location, module_from_spec
import argparse

# Chargement module
spec = spec_from_file_location('engine', '/path/to/engine.py')
engine = module_from_spec(spec)
spec.loader.exec_module(engine)

# Création run
run_id = engine.make_run_dir().name

# Exécution
result = engine.run_passes(
    Path('/path/to/runs') / run_id,
    argparse.Namespace(
        topic='Sujet ANU',
        mode=7,
        pass_id='p1',
        input=None,
        run_id=run_id,
    ),
)

# Accès résultat
print(result['status'], result['last_pass'], result['output_file'])
```

**Important** : l’appel via CLI (`python engine.py --topic ... --mode ... --pass ... --run-id ...`) écrit les fichiers mais n’imprime pas le résultat structuré. L’appel programmatique retourne le dict complet.

### 5.2 Appel CLI

```bash
python3 engine.py --topic "Sujet" --mode 7 --pass p1 --run-id 20260701_165041
```

Sortie : manifest JSON sur stdout.

---

## 6. Contrat API Stepfun/Nous

### 6.1 Endpoint

```
POST https://inference-api.nousresearch.com/v1/chat/completions
```

### 6.2 Authentification

```
Authorization: Bearer <access_token>
Content-Type: application/json
```

Token rafraîchi automatiquement sur 401/403 via OAuth2 refresh.

### 6.3 Payload

```json
{
  "model": "stepfun/step-3.7-flash:free",
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."}
  ],
  "max_tokens": 8192,
  "temperature": 0.2
}
```

### 6.4 Réponse (format confirmé live)

```json
{
  "id": "gen-...",
  "model": "stepfun/step-3.7-flash-20260528:free",
  "provider": "StepFun",
  "choices": [{
    "message": {
      "content": null,
      "reasoning": "Texte utile...",
      "reasoning_details": [{
        "type": "reasoning.text",
        "text": "Texte utile..."
      }]
    }
  }]
}
```

### 6.5 Extraction de texte

Ordre dans `engine.py` :
1. `message.content`
2. `message.reasoning`
3. `message.reasoning_details[*].text` où `type == "reasoning.text"`

### 6.6 Modèles valides

- Plan gratuit : `stepfun/step-3.7-flash:free`
- Plan payant : `stepfun/step-3.7-flash`
- Règle : préfixe `vendor/model` obligatoire, suffixe `:free` autorisé

---

## 7. Gestion des erreurs

### 7.1 Niveaux d’erreur

| Code/Signal | Comportement |
|---|---|
| HTTP 404 modèle | Retour `[LLM ERROR] HTTP 404: ...` |
| HTTP 401/403 | Refresh token + nouvel appel. Si échec → arrêt définitif |
| Timeout >60s | Retour `[LLM ERROR] HTTP ...: Timeout` |
| Réponse sans choix | Retour `[LLM ERROR]` |
| Exception dans workflow | Checkpoint `status: failed`, `errors` peuplé |

### 7.2 Circuit breaker

- Pas de retry automatique sur 401/403 après échec du refresh
- Arrêt propre avec checkpoint d’erreur

---

## 8. Sécurité

### 8.1 Secrets

- Aucun token en clair dans `engine.py`, `SKILL.md` ou les docs de référence
- Masquage via `_mask_token()` : format `sk-****...xxxx`
- Chemins auth/config référencés, jamais contenus

### 8.2 Injections

- Pas d’`input()` dans `engine.py`
- Entrées utilisateur : `--topic` et `--input` uniquement
- Pas d’`eval()`, `exec()`, `subprocess`
- Checkpoints JSON validés par schéma implicite

### 8.3 Validation webhooks (hors scope ANU)

Gérée par Hermes, pas par ANU.

---

## 9. Logs et observabilité

| Fichier | Contenu | Niveau |
|---|---|---|
| `~/.hermes/profiles/dev/logs/hermes_YYYY-MM-DD.log` | Sessions ANU | AUTONOMOUS |
| `<run_id>/p*.json` | Checkpoints par passe | N/A (fichiers) |
| `<run_id>/.manifest.json` | Agrégat passes | N/A (fichiers) |

---

## 10. Tests et vérifications

| Test | Résultat |
|---|---|
| `py_compile engine.py` | ✅ |
| Import + 7 modes | ✅ |
| `_resolved_model('auto')` | ✅ `stepfun/step-3.7-flash:free` |
| `_resolved_base_url()` | ✅ `.../v1/chat/completions` |
| `llm_generate()` backend | ✅ HTTP 200 |
| Extraction réponse Stepfun | ✅ Confirmé live |
| Modes 1-7 | ✅ `status: completed` |
| Zéro ref Google/Gemini | ✅ |
| `run_passes()` retour dict | ✅ |

---

## 11. Gouvernance

- **Versioning** : manuel via `SKILL.md` frontmatter
- **Backups** : `backups/engine_YYYYMMDD_HHMMSS.bak` avant modification critique
- **Commits** : aucun automatique dans ce skill
- **Documentation** : `ns-documentation.md` pour les bonnes pratiques NS

---

## 12. Points de vigilance

1. **Dépendance Hermes** : ANU ne fonctionne pas sans Hermes configuré
2. **Suffixe `:free`** : ne pas le tronquer, il est nécessaire pour le plan gratuit
3. **Rate limit** : `nous_rate_guard` peut skipp ANU temporairement
4. **Modèle recommandé** : ANU utilise le modèle configuré, pas le Portal `/api/nous/recommended-models`
5. **Documentation NS hors ligne** : doc officielle Nous inaccessible, règles dérivées du code Hermes + live API
