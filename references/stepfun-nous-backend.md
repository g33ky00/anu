# Stepfun/Nous Backend Notes

## Endpoint
`POST {inference_base_url}/chat/completions`

## Auth
- Reuse `~/.hermes/auth.json` active provider tokens.
- On 401/403: refresh via `{portal_base_url}/oauth2/token` with `grant_type=refresh_token`.
- Stop on persistent auth failure; do not retry indefinitely.

## Model Resolution
- Use `model: auto` in `engine.py`.
- Resolve to `config.yaml -> model.default`, fallback `stepfun/step-3.7-flash:free`.

## Response Quirk
- Some Stepfun responses return `message.content = null`.
- Useful text may be in `message.reasoning` or `message.reasoning_details[].text` with `type=reasoning.text`.
- `engine.py` now extracts those fields before writing `p*.md`.

## Failure Surface
- HTTP != 200 or missing `choices[0].message` text after extraction → `[LLM ERROR ...]`.
- Do not ship `[DRY-RUN ...]` or `[LLM ERROR ...]` as ANU output.
