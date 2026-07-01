# Documentation NS — Structuration et développement d’ANU

## 1. Vue d’ensemble

ANU Mind est un moteur multi-passes (4 passes) conçu pour produire des raisonnements structurés sur un sujet donné, via 7 archétypes/modes définis dans `references/modes.md`.

**Principe d’exécution** : pas d’interface interactive, pas d’appel API codé en dur. Hermes exécute `engine.py` via `execute_code`, le skill dicte la séquence, les critères de passage et les formats de sortie.

## 2. Architecture des composants

```
anu_mind/
├── scripts/
│   └── engine.py              # Moteur principal : auth, LLM backend, workflow
├── references/
│   ├── modes.md               # Spécifications des 7 modes (inchangées)
│   ├── provider-backend.md    # Notes fournisseur/backend
│   ├── stepfun-nous-backend.md # Notes spécifiques Stepfun/Nous
│   └── nous-model-naming.md   # Règles de nommage de modèles pour Nous
├── templates/
│   └── checkpoint_v1.json     # Schéma de checkpoint
└── SKILL.md                   # Définition du skill
```

## 3. Méthodes de déclaration des composants

### 3.1 `engine.py` — Composant principal

**Déclaration** : module Python autonome, sans dépendances fournisseur.

- `_load_config()` : lit `~/.hermes/config.yaml`, extrait `provider`, `model.default`, `base_url`, `api_key`
- `_load_auth()` : lit `~/.hermes/auth.json`, sélectionne le provider actif ou `nous`
- `_resolved_model()` : retourne le modèle configuré, sans transformation du suffixe
- `_resolved_base_url()` : construit l’URL endpoint depuis config ou auth
- `_refresh_access_token()` : rafraîchit le token via OAuth2 `refresh_token`
- `_http_json()` : appel HTTP POST JSON avec gestion d’erreur HTTP
- `_llm_backend()` : orchestrateur LLM avec rafraîchissement auto sur 401/403
- `llm_generate()` : interface publique utilisée par `run_passes()`
- `run_passes()` : workflow principal des 4 passes

**Convention d’appel** : `llm_generate(model="auto", user_prompt=..., system_instruction=..., max_tokens=..., temperature=...)`

Le paramètre `model="auto"` est la convention nominative. `auto` signifie : résoudre depuis `config.yaml`. Tout autre valeur explicite est passée telle quelle à l’API.

### 3.2 `references/modes.md` — Déclaration des modes

**Format** : Markdown structuré par mode.

Chaque mode déclare :
- `name` : nom archétypal
- `temperature` : valeur flottante
- `system_prompt_template` : template utilisé
- `max_output_tokens` : budget tokens
- `output_constraints` : contraintes de formatage

**Convention d’appel** : `MODES[mode_id]` retourne le dictionnaire du mode. Le mode 2 (CODER) est le fallback si l’archétype demandé n’existe pas.

### 3.3 `templates/checkpoint_v1.json` — Schéma de checkpoint

**Déclaration** : JSON Schema implicite, documenté dans `SKILL.md`.

Champs obligatoires :
- `$schema` : `"checkpoint_v1"`
- `run_id` : identifiant horodaté `YYYYMMDD_HHMMSS`
- `pass_id` : `p1` | `p2` | `p3` | `p4`
- `mode_id` : entier 1-7
- `topic` : sujet brut ANU
- `input_file` : chemin relatif ou `null`
- `output_file` : chemin de sortie Markdown
- `metrics` : `tokens_in`, `tokens_out`, `wall_time_s`
- `status` : `completed` | `skipped` | `failed`
- `score` : mapping dimensions 0-10 pour P2, `null` sinon
- `errors` : tableau d’erreurs

**Convention d’écriture** : un checkpoint par passe, écrit dans le répertoire de run `<run_id>/`.

### 3.4 `references/provider-backend.md`, `stepfun-nous-backend.md`, `nous-model-naming.md`

**Déclaration** : documents Markdown de référence, lus à la demande.

Ils documentent :
- Endpoint et auth Hermes réutilisés
- Quirk de réponse Stepfun (`message.content` peut être `null`, extraire `reasoning`/`reasoning_details`)
- Règle de nommage de modèle pour Nous

## 4. Méthodes d’appel des composants

### 4.1 Séquence d’appel ANU

1. Charger `SKILL.md` et `references/modes.md`
2. Créer le répertoire de run : `run_id = YYYYMMDD_HHMMSS`
3. Sélectionner `mode_id`
4. Appeler `engine.py` pour chaque passe :
   ```
   engine.py --topic "<sujet>" --mode <mode_id> --pass <p1|p2|p3|p4> --run-id <run_id> [--input <fichier_md>]
   ```
5. Lire le checkpoint JSON de la passe pour vérifier `status`
6. Livrer `pass4.md` et les formats machine si demandés

### 4.2 Appel LLM interne

```
llm_generate(
    model="auto",
    user_prompt=...,
    system_instruction=mode["system_prompt_template"],
    max_tokens=mode["max_output_tokens"],
    temperature=mode["temperature"],
)
```

Résolution du modèle :
- `model != "auto"` → passage direct
- `model == "auto"` → lecture `config.yaml → model.default`, fallback `stepfun/step-3.7-flash:free`

Appel HTTP :
- `POST {base_url}/chat/completions`
- Auth : Bearer token depuis `auth.json`, rafraîchi automatiquement sur 401/403
- Extraction du texte : `message.content` → `message.reasoning` → `message.reasoning_details[*].text`

### 4.3 Extracteur de texte (contrat API confirmé)

Réponse Stepfun/Nous format confirmé :
```json
{
  "choices": [{
    "message": {
      "content": null,
      "reasoning": "Texte utile...",
      "reasoning_details": [{"type": "reasoning.text", "text": "Texte utile..."}]
    }
  }]
}
```

Ordre d’extraction dans `engine.py` :
1. `message.content`
2. `message.reasoning`
3. `message.reasoning_details` où `type == "reasoning.text"` → `text`

## 5. Gestion des erreurs et rollback

### 5.1 Niveaux d’erreur

| Erreur | Comportement |
|---|---|
| HTTP 404 modèle inconnu | Retour `[LLM ERROR] HTTP 404: ...` |
| HTTP 401/403 | Rafraîchissement token unique, nouvel appel. Si échec → arrêt définitif. |
| Timeout (>60s) | Retour `[LLM ERROR] HTTP <status>: Timeout` |
| Réponse sans `choices` ou `message` | Retour `[LLM ERROR]` avec détail |

### 5.2 Rollback

**Backups** : `/home/g33ky/.hermes/profiles/dev/skills/anu_mind/backups/engine_20260701_153937.bak`

Restoration : `cp backups/engine_20260701_153937.bak scripts/engine.py`

**Rollback disponible** : OUI — commande ci-dessus, impact arrêt des sessions ANU, délai <5s.

## 6. Vérification et tests

### 6.1 Vérification crypto/identity

- Aucun token/clé en clair dans les fichiers de skill, run, ou documentation
- Tokens masqués via `_mask_token()` dans `engine.py` : format `sk-****...xxxx`
- Référence aux chemins uniquement, jamais au contenu

### 6.2 Injections / prompts malveillants

- `run_passes()` n’utilise pas `input()` — aucune exécution interactive
- Toute entrée utilisateur est canalisée via `--topic` et `--input`
- Aucune référence à `eval()`, `exec()`, `subprocess` dans `engine.py`
- Checkpoint schema valide JSON unique par passe

### 6.3 Tests effectués

| Test | Résultat |
|---|---|
| `py_compile engine.py` | ✅ Succès |
| Import module + modes | ✅ 7 modes chargés |
| `_resolved_model('auto')` | ✅ `stepfun/step-3.7-flash:free` |
| `_resolved_base_url()` | ✅ `.../v1/chat/completions` |
| `llm_generate()` backend | ✅ Réponse live 200 |
| Contrat API extracteur | ✅ Confirmé live |
| Modes 1 à 7 | ✅ `status: completed` |
| Zéro ref Google/Gemini | ✅ Confirmé par grep |

## 7. Points de vigilance et limites

- **Dépendance Hermes** : `engine.py` dépend de `~/.hermes/config.yaml` et `auth.json`. Si Hermes n’est pas configuré, ANU ne fonctionne pas.
- **Suffixe `:free`** : il est autorisé et nécessaire pour le plan gratuit Nous. Ne pas le tronquer.
- **Rate limit** : le code Hermes inclut un `nous_rate_guard`. Si un autre run appelle Nous en parallèle, ANU peut être skippé temporairement.
- **Modèles recommandés** : ANU utilise le modèle configuré, pas le Portal `/api/nous/recommended-models`. Si le compte change de plan, mise à jour manuelle de `config.yaml` requise.
- **Documentation NS hors ligne** : la doc officielle Nous Research est inaccessible dans l’environnement courant. Les règles documentées ici sont dérivées du code Hermes installé et de la vérification API live.

## 8. Gouvernance et versioning

- Skills versionnés manuellement via `SKILL.md` frontmatter
- Backups horodatés avant modification critique
- Aucun commit automatique dans ce skill
- Logs Hermes : `AUTONOMOUS` pour chaque session ANU dans `~/.hermes/profiles/dev/logs/hermes_YYYY-MM-DD.log`
