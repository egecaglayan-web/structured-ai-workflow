import asyncio
import hashlib
import json
import logging

from .ai import AIUnavailable, fallback_brief
from .models import Brief, Citation, ProcessRequest, ProcessResult
from .retrieval import retrieve
from .store import Conflict

logger = logging.getLogger(__name__)


class Workflow:
    def __init__(self, settings, ai, notifier, store, chunks):
        self.settings, self.ai, self.notifier = settings, ai, notifier
        self.store, self.chunks = store, chunks
        self.lock = asyncio.Lock()
        self.in_flight: set[str] = set()
        self.provider = "demo" if settings.demo_mode else settings.ai_provider

    async def degraded(self, request: ProcessRequest, code: str) -> ProcessResult:
        logger.warning("event=workflow_fallback request_id=%s code=%s", request.request_id, code)
        notified = await self.notifier.notify(str(request.request_id), code)
        return ProcessResult(
            request_id=request.request_id, mode="fallback", provider=self.provider, brief=fallback_brief(), citations=[],
            error_code=code,
            warning=("The service owner must check provider billing or credits before AI processing can resume. Review the input manually."
                     if code == "provider_quota" else "AI processing failed. Review the input manually.")
            + (" Owner notification also failed; contact the owner directly." if not notified else ""),
        )

    async def process(self, request: ProcessRequest) -> ProcessResult:
        request_id = str(request.request_id)
        digest = hashlib.sha256(json.dumps(
            {"text": request.text, "use_references": request.use_references}, sort_keys=True
        ).encode()).hexdigest()
        async with self.lock:
            self.store.prune()
            found, previous = self.store.find(request_id, digest)
            if found and previous:
                logger.info("event=request_replayed request_id=%s", request.request_id)
                return previous
            if request_id in self.in_flight:
                raise Conflict("This request is still processing. Retry later with the same request ID.")
            if not found:
                self.store.reserve(request_id, digest)
            self.in_flight.add(request_id)
        try:
            if found:
                # A crash after reservation must not blindly repeat a potentially billed request.
                result = await self.degraded(request, "previous_request_interrupted")
                async with self.lock:
                    self.store.finish(result)
                return result
            sources = retrieve(request.text, self.chunks) if request.use_references else []
            try:
                brief = Brief.model_validate(await self.ai.generate(request.text, sources))
                lookup = {s.source_id: s for s in sources}
                if any(source_id not in lookup for source_id in brief.source_ids):
                    raise AIUnavailable("invalid_sources")
                citations = [Citation(**vars(lookup[sid])) for sid in dict.fromkeys(brief.source_ids)]
                # Demo displays retrieved evidence without pretending the canned result used it.
                if self.settings.demo_mode:
                    citations = [Citation(**vars(s)) for s in sources]
                warning = None
                if self.settings.demo_mode:
                    warning = "Offline demo: template result; excerpts are retrieved examples, not AI citations."
                elif request.use_references and not sources:
                    warning = "No matching reference was found. Treat policy details as unverified."
                elif request.use_references and not citations:
                    warning = "The model cited no reference. Treat policy details as unverified."
                result = ProcessResult(
                    request_id=request.request_id, mode="demo" if self.settings.demo_mode else "live", provider=self.provider,
                    brief=brief, citations=citations, warning=warning,
                )
            except AIUnavailable as error:
                result = await self.degraded(request, error.code)
            except Exception:
                result = await self.degraded(request, "processing_error")
            async with self.lock:
                self.store.finish(result)
            logger.info("event=workflow_completed request_id=%s mode=%s category=%s sources=%d",
                        request.request_id, result.mode, result.brief.category, len(result.citations))
            return result
        finally:
            async with self.lock:
                self.in_flight.discard(request_id)
