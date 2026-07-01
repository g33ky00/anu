# Nous Inference — Model Naming Rule (source: Hermes codebase + live API verification)

Endpoint: `https://inference-api.nousresearch.com/v1/chat/completions`
Provider normalization class: `nous` is an aggregator (`_AGGREGATOR_PROVIDERS`), so calls expect vendor-prefixed slugs.

## Rule
- Use `vendor/model` identifiers.
- For Nous Portal free-tier entitlement, append `:free` to the slug in the `model` field.
- Free-tier eligibility is account-entitlement based, resolved via:
  - `GET /api/nous/recommended-models` (`freeRecommendedModels`)
  - helpers: `check_nous_free_tier()`, `partition_nous_models_by_tier()`

## Examples
Valid free: `stepfun/step-3.7-flash:free`
Valid paid: `stepfun/step-3.7-flash`
Invalid: bare non-prefixed names like `step-3.7-flash`

## ANU engine impact
`_resolved_model()` must return the slug as configured in `config.yaml` (e.g. `stepfun/step-3.7-flash:free` for free-tier usage). Do not strip the `:free` suffix before API calls.
