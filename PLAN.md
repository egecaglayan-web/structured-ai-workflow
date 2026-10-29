# Structured AI Workflow

Build one text-to-structured-brief feature with FastAPI, configurable OpenAI/Anthropic structured outputs, and a lightweight React UI. OpenAI remains the default.

Flow: React form → validate/authenticate → briefly locked persistent request reservation → optional local lexical retrieval → concurrent calls to the selected provider with a portable schema → local size/source validation → briefly locked result persistence → reviewable result with provider attribution. Concurrent duplicates return 409; provider failures return an explicitly marked fallback and notify the owner. Billing/quota failures remain distinct from rate limits and tell users that the owner must check billing.

| n8n equivalent | Implementation |
|---|---|
| Form Trigger / Webhook | `frontend/src/App.jsx`, `app/main.py` |
| Code / Set / IF | `app/models.py`, `app/retrieval.py`, `app/service.py` |
| OpenAI / Anthropic node | `app/ai.py`: configurable real adapters and deterministic demo |
| Error Trigger / HTTP Request | `app/notifier.py` (real and demo) |
| Executions / deduplication | `app/store.py`, SQLite volume, single worker |

The client supplies the selected provider's account/key/model access, app access code, notification webhook, approved documents, and hosting account. Missing selected-provider settings enable an offline demo; there is no automatic switch to another paid provider. Defaults: OpenAI, configurable Anthropic model `claude-haiku-5-5`, English text, a small read-only Markdown/TXT corpus, one shared internal team, 24-hour result retention, one model call per new request, local delivery. Results require human review; no generated content is sent externally. Excludes uploads, embeddings/vector services, multi-tenant accounts, streaming, autonomous agents, and deployment.

Configuration loads the project-root `.env` without overriding the process environment. Local secrets can be entered with `python -m app.set_secret NAME`. Runtime and development dependencies are separate; internal analysis, proposal, and validation notes are excluded from Git and Docker context.

`app.check` performs a read-only lookup for the selected provider; `--ai` (legacy alias `--openai`) allows one billable synthetic probe. Both adapters use the same prompt/data envelope, explicit timeouts, no SDK retries, and isolated HTTP transports. Neither path is claimed to have been live-tested in this delivery.
