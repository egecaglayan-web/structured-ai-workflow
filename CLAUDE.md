# Project maintenance

The parent CLAUDE.md applies when present.

This project implements one text-to-brief workflow.
React submits a request to FastAPI; optional lexical retrieval supplies context.
The selected OpenAI/Anthropic provider produces a brief; the server validates it and attaches known excerpts.
Every output is a draft for human review.

## File map

- `app/config.py`: project-root .env loading, environment overrides, safe diagnostics.
- `app/set_secret.py`: hidden local secret entry preserving other .env assignments.
- `app/models.py`: strict input/output contract and allowed categories.
- `app/main.py`: lifespan, bounded body reading, access checks, API, built UI.
- `app/service.py`: request workflow and fallback orchestration.
- `app/ai.py`: OpenAI/Anthropic adapters, provider factory, safe errors, and demo.
- `app/retrieval.py`: small UTF-8 text corpus, chunking, keyword retrieval.
- `app/notifier.py`: metadata-only owner alerts and offline notifier.
- `app/store.py`: persistent request reservation/result journal.
- `app/check.py`: read-only setup validation; optional billable AI probe.
- `app/demo.py`: offline ASGI round-trip with synthetic input.
- `frontend/src/App.jsx`: form, references, reviewable output, JSON view.
- `tests/`: offline backend tests and mock transport integration tests.
- `frontend/src/App.test.jsx`: user interaction and replay-ID tests.

## Project invariants

- Keep request IDs stable across retries of identical input.
- A changed input under an existing request ID must return 409.
- Reserve the journal row before the potentially billed call.
- Hold the lock only for journal operations; independent AI calls run concurrently.
- Return 409 for a concurrent duplicate; never start another provider call for it.
- An interrupted reservation must never automatically repeat that call.
- Keep one worker and one deployment replica; the lock and limiter are local.
- Preserve the SQLite volume across redeployments for retained deduplication.
- Never label demo/fallback results as live AI processing.
- Source IDs must come from the retrieved subset, not the entire corpus.
- Citation excerpts and document names are assembled by code.
- The demo's retrieved excerpts are not evidence used by an LLM.
- References are operator-controlled local files; no public upload endpoint exists.
- Never enable API retries implicitly; costs and interrupted requests need review.
- Keep OpenAI the default; missing selected-provider settings enable demo, not paid failover.
- Both adapters use the same prompt/data envelope and ProviderBrief → Brief validation.
- Keep provider_quota distinct from rate limits; notify the owner and show billing guidance.
- Keep app access codes distinct from server-side provider keys.
- Do not add secrets to Vite configuration or frontend environment variables.
- Generated content is never automatically sent to third parties.

## Commands

```sh
python -m pip install -r requirements-dev.txt
pytest -q
python -m app.check
python -m app.demo
npm --prefix frontend ci
npm --prefix frontend test
npm --prefix frontend run build
python -m uvicorn app.main:app --workers 1 --no-access-log
```

## Known traps

- Missing live settings intentionally select demo, even if DEMO_MODE=false.
- Model availability and structured-output compatibility need real account checks.
- Model lookup is read-only; `check --ai` is a billable selected-provider probe (`--openai` alias).
- Cache replays retain original provider attribution; use a new run after configuration changes.
- Webhooks have no safe generic read-only delivery check; the checker never sends.
- Replays include cached fallbacks; a deliberate new run gets a new request ID.
- Browser reload loses its in-memory pending ID and application access code.
- TTL cleanup deletes rows, not operator backups or SQLite free pages.
- Lexical RAG misses synonyms; evaluate before adding embeddings.
- Process environment overrides .env, including after local secret updates; restart after changes.
- Railway volumes are root-owned; follow the README's documented runtime UID setup.
- The CI workflow assumes this folder becomes its own repository root.
