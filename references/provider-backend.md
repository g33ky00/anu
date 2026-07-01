# Provider / Backend Rules

- `engine.py` reads Hermes model/provider configuration from `~/.hermes/config.yaml` and reuses `~/.hermes/auth.json` for access/refresh tokens.
- No provider-specific env vars are required for ANU; it inherits the active Hermes provider/model.
- Runtime model passed to `llm_generate()` remains generic, eg `auto`, resolved to the configured default during execution.

## Scoping

- The concrete backend adapter is limited to the active Hermes provider. Custom providers may be added only via a documented adapter path, not by ad-hoc env-var parsing inside `engine.py`.
