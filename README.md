# Brief Studio — Structured AI Workflow

A small, complete example of one AI automation feature. Enter a request in React, optionally retrieve reference excerpts, and receive a validated brief from a Python/FastAPI workflow using OpenAI or Anthropic Claude.

## What it does

- Returns a summary, one allowed category, suggested next steps, source excerpts, and review status.
- Defaults to the OpenAI Responses API with a strict provider schema and `store=False`. Set `AI_PROVIDER=anthropic` to use Claude's Messages API with JSON structured outputs in `output_config.format`. Both paths use the same system prompt and JSON data envelope, parse into `ProviderBrief`, and validate string/item limits with the local `Brief` model.
- Labels each result with `provider: openai|anthropic|demo`; the UI shows a small provider badge beside the result heading. No automatic failover to another paid provider occurs.
- Retrieves up to three matching chunks from a small, operator-managed UTF-8 Markdown/TXT collection. This is lexical RAG, with no embedding service or vector database.
- Provides an offline template demo whenever required service settings are missing. The demo does **not** simulate LLM quality; its excerpts are labeled as retrieved examples.
- Handles authentication errors, quota/billing failures, rate limits, provider overload, connection errors, timeouts, refusals, incomplete responses, invalid output, and unknown source IDs. Failures return a clearly marked fallback, never a fabricated assessment. Quota failures tell the user that the service owner must check provider billing/credits and send an owner alert.
- Journals request IDs in SQLite before a potentially billed call. Repeated IDs replay the stored response; changed inputs under the same ID return 409. An interrupted request returns a manual-review fallback instead of repeating the call.

| n8n concept | Code |
|---|---|
| Form Trigger / Webhook | React form / `POST /api/process` |
| Set / validation | `app/models.py` |
| Code / document lookup | `app/retrieval.py` |
| OpenAI / Anthropic node | `app/ai.py`: `OpenAIAI` / `AnthropicAI`, selected by configuration |
| Workflow connections | `app/service.py` |
| Error Trigger / HTTP Request | `app/notifier.py` |
| Execution deduplication | `app/store.py` |

## Try it now

Use Python 3.12 and Node 24. Run from this project directory. No account or secrets are needed for the default demo.

```sh
python -m pip install -r requirements.txt
npm --prefix frontend ci
npm --prefix frontend run build
python -m app.demo
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

Open <http://127.0.0.1:8000>, choose a sample, and select **Generate brief**. Try both reference settings and the JSON view. The built UI is served by FastAPI, so it uses the same origin as the API. For UI development, start the backend and run `npm --prefix frontend run dev`; Vite proxies `/api` and `/health` to port 8000.

## AI provider

`AI_PROVIDER` is a server setting: `openai` (default) or `anthropic`. Only the selected provider's key/model and the shared access-code/notification settings are required for live mode. Missing selected-provider settings activate the offline demo, even if the other provider is configured. Set `DEMO_MODE=false` after setup and restart the service. Neither paid provider path is claimed to have been live-tested here; generation tests use mocked HTTP transports.

### OpenAI (default)

1. Use a **client-owned** OpenAI API project. In the platform, select the intended project and open **API keys** to create a server-side project key.
2. Ensure API billing and model access are enabled. Pick a model available to the project that supports Responses structured outputs; set its exact ID in `OPENAI_MODEL`. No model is hard-coded because availability changes.
3. Set `OPENAI_API_KEY` in the process environment or hosting **Variables**. Do not paste it into chat, put it in frontend code, or commit it.
4. Set a client-approved API budget and usage alerts. One fresh request attempts one model call, with SDK retries disabled and an output-token cap. The local request limit is a guardrail, not a provider spending cap.
5. Run `python -m app.check` for a read-only model lookup. If desired, `python -m app.check --ai` performs **one billable structured-output probe** on the selected provider. Model lookup alone does not verify generation quality, billing readiness, or structured-output compatibility.

Implementation follows [official OpenAI structured-output guidance](https://developers.openai.com/api/docs/guides/structured-outputs) and [API error guidance](https://developers.openai.com/api/docs/guides/error-codes). A valid schema or recognized citation ID does not prove factual correctness.

### Anthropic Claude

1. Use a **client-owned** Claude Console account/API workspace. In the Console's **API keys** screen, create a server-side key and configure API billing/credits in **Billing**. Confirm that the intended model is available to that account.
2. Set `AI_PROVIDER=anthropic` and store the key as `ANTHROPIC_API_KEY` in hosting **Variables**, or enter it locally with `python -m app.set_secret ANTHROPIC_API_KEY`.
3. `ANTHROPIC_MODEL` defaults to `claude-haiku-5-5`, the configured reference-project value requested for this integration. It remains configurable; no account access or model availability is assumed from this default.
4. Configure the shared `APP_ACCESS_TOKEN` and `OWNER_WEBHOOK_URL`, set `DEMO_MODE=false`, and restart. No OpenAI credentials are needed for this selection. Choose an approved API budget, monitor credits/usage, and keep all provider keys out of frontend code.
5. Run `python -m app.check` for `GET /v1/models/{model_id}` on the selected Anthropic model. `--ai` allows one billable synthetic generation request. If the installed SDK lacks a model-lookup method, the checker warns explicitly that connectivity was not verified rather than sending a generation request implicitly.

The adapter uses Anthropic's [current JSON structured-output format](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) through `output_config.format`, as described in its raw-schema example, plus the [read-only model lookup](https://platform.claude.com/docs/en/api/models/retrieve). HTTP errors follow the [Claude error guidance](https://platform.claude.com/docs/en/api/errors). SDK retries are disabled, external requests use explicit timeouts, and the transport ignores ambient proxy/base-URL settings. A refusal or truncated output returns a marked fallback.

`python -m app.check --openai` remains a backward-compatible alias for `--ai`; it probes the **selected** provider, including Anthropic. It does not force OpenAI. These probes are optional and are not part of offline tests. Never run them against client accounts without the client's approval.

## Service setup

### Owner notifications

1. Ask the client to create an HTTPS Incoming Webhook accepting a JSON object with a `text` field, such as a Slack-compatible incoming webhook.
2. Put that URL in `OWNER_WEBHOOK_URL` through the hosting **Variables** screen. Treat the entire URL as a secret.
3. Workflow failures send only the request ID and a bounded error code. User input, generated content, API keys, and provider exception messages are excluded.
4. The check command validates the URL format but deliberately sends no message. Test actual delivery only with the client's explicit approval. A delivery failure produces a safe error log and a visible user warning for workflow fallbacks.

### Access and documents

1. Generate a random access code of at least 32 characters outside this repository. Set `APP_ACCESS_TOKEN` on the server and share it with authorized team members through the client's approved channel.
2. Users enter this **application access code** in the UI. It stays in page memory and is sent in the Authorization header; it is not a provider API key. There are no user accounts, roles, or tenant boundaries in this example.
3. Put approved UTF-8 `.md` / `.txt` files in `reference_docs/`, replacing the fictional examples. Maximum: 30 regular files, 100 KB each; nested folders, symlinks, uploads, and PDFs are not supported. Restart after changes.
4. Configure the selected provider's key/model and both shared settings, then set `DEMO_MODE=false`. Anthropic's model has a default; OpenAI's model must be provided. Missing required values keep the service in offline demo mode, with a startup warning and UI banner. Invalid complete live settings fail validation.

For local setup, copy the supplied `.env.example` to a file named `.env` in the project root using your editor. Set non-secret settings such as `AI_PROVIDER`, the selected model, and `DEMO_MODE` there. The application loads this exact file with `python-dotenv`; process/platform environment variables always take precedence. Values are read literally without variable interpolation.

Enter local secrets through the helper, which prompts twice using hidden input. The two provider-key commands below are alternatives; run only the one for your selected provider, plus the shared access-code and notification commands:

```sh
python -m app.set_secret OPENAI_API_KEY
python -m app.set_secret ANTHROPIC_API_KEY
python -m app.set_secret APP_ACCESS_TOKEN
python -m app.set_secret OWNER_WEBHOOK_URL
```

The helper creates or updates the project-root `.env`, preserves other assignments and comments, and never prints the secret value. It refuses to use an echoing fallback if hidden terminal input is unavailable. Run it in your own terminal; do not provide secrets as command arguments or in chat. Restart the application after changes. Local file permissions and access to the machine remain the operator's responsibility. On hosted deployments, enter secrets directly in the platform's **Variables** screen instead.

| Variable | Default | Purpose |
|---|---|---|
| `DEMO_MODE` | Auto demo if required values are missing | Set `true` to force offline behavior; the local template starts with `true` |
| `AI_PROVIDER` | `openai` | Select `openai` or `anthropic`; other values fail validation |
| `OPENAI_API_KEY` | Empty | Required only for live OpenAI requests, server only |
| `OPENAI_MODEL` | Empty | Required only for OpenAI; must support structured outputs |
| `ANTHROPIC_API_KEY` | Empty | Required only for live Anthropic requests, server only |
| `ANTHROPIC_MODEL` | `claude-haiku-5-5` | Configurable Anthropic model; account availability must be checked |
| `APP_ACCESS_TOKEN` | Empty | Required live access code, at least 32 characters |
| `OWNER_WEBHOOK_URL` | Empty | Required live HTTPS notification webhook |
| `API_TIMEOUT_SECONDS` | `30` | External request timeout; 1–90 seconds |
| `MAX_OUTPUT_TOKENS` | `2000` | Output/reasoning token cap; 256–8000 |
| `REQUESTS_PER_MINUTE` | `10` | Global API submission limit per process, including replays; 1–120 |
| `CACHE_TTL_HOURS` | `24` | Result/reservation retention; 1–168 hours |
| `DATABASE_PATH` | Project `data/requests.sqlite3` | Persistent SQLite request journal |
| `REFERENCE_DIR` | Project `reference_docs` | Operator-managed read-only corpus |

Relative configured paths resolve from the process working directory. The default paths are project-relative. Time intervals use monotonic or Unix timestamps, independent of local timezone.

## Deploy with Docker / Railway

This repository is prepared for local delivery; deployment is performed by the owner after review.

1. Put this project directory at the root of its own repository. Add that repository as a service in your Railway project and use the included Dockerfile.
2. In the service's **Variables**, configure the live variables above. The platform may set `PORT`; the container honors it and otherwise uses 8000. Expose the service through HTTPS.
3. Attach a persistent volume mounted at `/app/data`. Select the application service, open **Variables**, and add `DATABASE_PATH` with value `/app/data/requests.sqlite3`. In the same screen add `RAILWAY_RUN_UID` with value `0`, apply the changes, and redeploy. Railway's [volume permissions documentation](https://docs.railway.com/volumes#permissions) says its volumes are mounted as root and recommends this setting for images using a non-root user. This override runs the service as root in its container; the Dockerfile otherwise keeps `appuser` as its default. If your deployment policy requires a non-root runtime, have the operator configure ownership of the mounted directory at startup instead. Image-build ownership does not set ownership of a later volume mount. These Railway steps are documented guidance and have not been tested on a live Railway service here. Without a persistent volume, restarts lose replay protection.
4. Run **exactly one worker and one service instance**. The Dockerfile enforces one Uvicorn worker; keep platform replicas at one. Horizontal scaling requires redesigning coordination and the rate limiter.
5. Configure `/health` as the health check. It shows process readiness and demo/live mode; it does not prove external provider health. Monitor error/fallback logs and owner-alert delivery as well.
6. Open the app, confirm **Live workspace**, then perform client-approved synthetic checks. Keep the access code, notification URL, and both providers' keys out of repository settings visible to frontend builds.

## API and validation

```http
POST /api/process
Content-Type: application/json
Authorization: Bearer <application-access-code-if-configured>

{
  "request_id": "8f5a4f32-ae25-4cc0-91ba-185810f7ba36",
  "text": "My password reset link is broken. How can I login?",
  "use_references": true,
  "website": ""
}
```

`website` is a bot trap and must stay empty. Inputs must contain 3–8,000 trimmed characters. Request bodies are limited to 32 KB, including streamed bodies. API schema documentation is disabled in the deployed app.

Success and AI fallbacks both return 200 with `mode: demo|live|fallback`, `provider: openai|anthropic|demo`, a validated `brief`, `citations`, `needs_human_review`, `warning`, and `error_code`. `provider` identifies the selected paid adapter for live/fallback processing, or `demo` for offline processing; it does not imply a successful generation. Inspect mode/error status before using the result. Protocol errors use 401, 403, 409, 413, 422, 429, or 503 with a safe `detail` message. A concurrent submission of the same request ID returns 409 with a message that it is still processing; retry later with the same ID to retrieve the completed result. Different request IDs can call the provider concurrently. Only journal lookup/reservation and completion use a brief local lock. The browser preserves an ID for retries in the same page session. **Start a new run** permits a fresh call, including retrying after a cached fallback or a provider/model change. Replays retain their original provider attribution; changing configuration does not regenerate a retained request. Reloading the page loses the browser's pending ID.

| Workflow error code | Meaning / action |
|---|---|
| `provider_auth` | 401/403; the owner checks the selected provider's key and permissions |
| `provider_quota` | Billing/credit/quota failure; the user sees owner-billing guidance and the owner receives an alert. Check credits/billing before starting a new run |
| `provider_rate_limit` | 429 rate/acceleration limit; retry only after the provider's limit recovers |
| `provider_error` | Provider errors including Anthropic 529/overload and 5xx; owner checks provider health |
| `provider_timeout` / `provider_connection` | Transport timeout or connection failure; check connectivity and configured timeout |
| `invalid_output` / `refused_or_incomplete` | Unusable, refused, truncated, or locally invalid response; review manually |
| `invalid_sources` | The model cited a source outside the retrieved subset; review manually |
| `processing_error` / `previous_request_interrupted` | Processing failed or an earlier attempt was interrupted; do not silently repeat a possibly billed call |

OpenAI 429 responses with `insufficient_quota` (including supported billing/spend-limit codes) map to `provider_quota`; `rate_limit_exceeded` maps to `provider_rate_limit`. Anthropic billing/credit codes and recognized low-credit messages map to `provider_quota`; ordinary 429 rate errors stay separate. The adapters inspect error metadata to choose a static code and never expose the provider's raw error body. No automatic retry or paid-provider switch is performed.

## Client handover notes

- Confirm real sample inputs, output fields, acceptance criteria, document formats/languages, daily volume, privacy constraints, model budget, notification channel, and hosting before adapting the example to production.
- All generated briefs require human review; nothing is automatically emailed or published. Prompt boundaries and source validation reduce risk but do not make the model immune to prompt injection or hallucinations.
- Keyword overlap can miss paraphrases and rank irrelevant passages. Source IDs, file names, and excerpt text are assembled from the local corpus by code, not invented by the model. Source-ID validation does not verify entailment. Evaluate actual examples before choosing embeddings or another retrieval approach.
- No raw input is stored by this application, but generated results and cited excerpts can still contain sensitive content. SQLite retains result/reservation data for the configured TTL; cleanup runs at startup, before requests, and about once per minute while running. Stopped services, database free pages, volumes, snapshots, and backups need an operator-managed deletion policy. Deduplication ends after expiry. Consider KVKK/GDPR with qualified counsel if personal data will be processed; no legal terms are supplied here.
- OpenAI calls set `store=False`. This parameter is not sent to Anthropic. Neither path makes a blanket claim about provider-side logging or retention; review the selected provider's data controls and the client's agreement separately.
- Only safe event metadata is logged. Input-validation/authorization failures, duplicate/in-progress responses, and rate limits do not send owner alerts, preventing trivial notification spam. Operational failures do; monitor startup errors and notification-delivery logs through hosting monitoring.
- If the process crashes after journal reservation, the request is deliberately not repeated automatically. Use manual review, then explicitly start a new run if appropriate. There is no exactly-once guarantee across expired/deleted journals or lost volumes.
- Docker image build, real provider calls, real webhook delivery, and hosted uptime must be verified in the client's environment before delivery is described as production-ready.

## Verification

```sh
python -m pip install -r requirements-dev.txt
pytest -q
python -m app.check
python -m app.demo
npm --prefix frontend test
npm --prefix frontend run build
```

Tests block real HTTP transports and use mocks, including both actual SDKs against mock transports. They check transmitted schemas, local output limits, provider selection, quota/rate separation, Anthropic overload, selected-model lookup, optional probe behavior, concurrent deduplication, field-name-only diagnostics, and hidden secret entry using temporary synthetic files. React tests cover sample submission, results, provider badges, billing guidance, references, JSON, non-JSON gateway errors, access-code handling, and replay IDs. `pytest` belongs to `requirements-dev.txt`; the Docker image installs only runtime dependencies from `requirements.txt`. GitHub Actions runs checks only; it does not host or schedule the application.

## File map

```text
app/                 configuration, API, AI, retrieval, workflow, alerts, journal, checks
frontend/            React source, component tests, Vite build, locked npm dependencies
reference_docs/      fictional sample policies (replace before real use)
tests/               offline backend tests
.github/workflows/   CI checks
PLAN.md              implementation scope
CLAUDE.md            project-specific maintenance instructions
```

## Possible later extensions

Add semantic retrieval only if real examples need it; then consider approved document ingestion, per-user identity, model-quality evaluations, or shared coordination for multiple instances. These are outside this focused feature.
