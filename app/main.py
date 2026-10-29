import asyncio
import logging
import secrets
import time
from collections import deque
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .ai import create_ai
from .config import ROOT, Settings, load_settings
from .models import ProcessRequest, ProcessResult
from .notifier import DemoNotifier, WebhookNotifier
from .retrieval import load_corpus
from .service import Workflow
from .store import Conflict, Store

logger = logging.getLogger(__name__)


class BodyLimit:
    """Bound streamed request bodies as well as requests with Content-Length."""

    def __init__(self, app, limit=32_000):
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in {"POST", "PUT", "PATCH"}:
            return await self.app(scope, receive, send)
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > self.limit:
                return await JSONResponse({"detail": "Request body is too large."}, status_code=413)(scope, receive, send)
            if not message.get("more_body", False):
                break
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if delivered:
                return await receive()
            delivered = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, bounded_receive, send)


def create_app(settings: Settings | None = None, ai=None, notifier=None) -> FastAPI:
    settings = settings or load_settings()
    arrivals = deque()

    @asynccontextmanager
    async def lifespan(app):
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
        # Provider SDK/HTTP loggers can contain paths and credential-bearing webhook URLs.
        for name in ("httpx", "httpcore", "openai", "anthropic"):
            logging.getLogger(name).setLevel(logging.CRITICAL)
        provider = ai or create_ai(settings)
        alerts = notifier or (DemoNotifier() if settings.demo_mode else WebhookNotifier(
            settings.owner_webhook_url.get_secret_value(), settings.api_timeout_seconds
        ))
        store = Store(settings.database_path, settings.cache_ttl_hours)
        app.state.workflow = Workflow(settings, provider, alerts, store, load_corpus(settings.reference_dir))
        stop = asyncio.Event()

        async def cleanup():
            while not stop.is_set():
                try:
                    await asyncio.wait_for(stop.wait(), timeout=60)
                except TimeoutError:
                    try:
                        store.prune()
                    except Exception:
                        logger.error("event=cache_cleanup_failed")
                        await alerts.notify("system", "cache_cleanup_failed")

        cleanup_task = asyncio.create_task(cleanup())
        if settings.demo_mode:
            logger.warning("event=startup mode=demo external_calls=disabled")
        else:
            logger.info("event=startup mode=live workers=1")
        try:
            yield
        finally:
            stop.set()
            await cleanup_task
            if ai is None and hasattr(provider, "close"):
                await provider.close()

    app = FastAPI(title="Structured AI Workflow", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(BodyLimit)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request, error):
        return JSONResponse(status_code=422, content={"detail": "Invalid input. Use a UUID request ID and 3–8,000 characters of text."})

    async def authorize(authorization: str | None = Header(default=None)):
        token = settings.app_access_token.get_secret_value()
        if token and not secrets.compare_digest((authorization or "").encode(), f"Bearer {token}".encode()):
            raise HTTPException(401, "Enter a valid application access code.")

    @app.get("/health")
    async def health():
        return {"status": "ok", "demo_mode": settings.demo_mode,
                "access_code_required": bool(settings.app_access_token.get_secret_value())}

    @app.post("/api/process", response_model=ProcessResult, dependencies=[Depends(authorize)])
    async def process(payload: ProcessRequest, request: Request):
        if payload.website:
            raise HTTPException(403, "Request could not be accepted.")
        now = time.monotonic()
        while arrivals and arrivals[0] <= now - 60:
            arrivals.popleft()
        if len(arrivals) >= settings.requests_per_minute:
            raise HTTPException(429, "Request limit reached. Try again in a minute.", headers={"Retry-After": "60"})
        arrivals.append(now)
        workflow = request.app.state.workflow
        try:
            return await asyncio.wait_for(workflow.process(payload), timeout=settings.api_timeout_seconds * 2 + 15)
        except Conflict as error:
            raise HTTPException(409, str(error)) from None
        except Exception:
            logger.error("event=request_failed request_id=%s", payload.request_id)
            await workflow.notifier.notify(str(payload.request_id), "request_failed")
            raise HTTPException(503, "Processing is unavailable. Retry with the same request ID.") from None

    dist = ROOT / "frontend/dist"
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/")
    async def index():
        if not (dist / "index.html").is_file():
            return JSONResponse({"detail": "Build the React UI first: cd frontend && npm ci && npm run build"}, status_code=503)
        return FileResponse(dist / "index.html")

    return app


app = create_app()
