"""Read-only configuration validation. No messages are sent by this command."""
import argparse
import asyncio

import httpx
import anthropic
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI, APIStatusError, APITimeoutError

from .ai import AIUnavailable, create_ai, status_error_code
from .config import SettingsError, load_settings
from .retrieval import load_corpus


async def check(ai_probe=False):
    stage, names = "settings", "SETTINGS"
    try:
        settings = load_settings()
        print("OK: settings validated.")
        stage, names = "reference docs", "REFERENCE_DIR"
        chunks = load_corpus(settings.reference_dir)
        print(f"OK: reference docs validated; chunks={len(chunks)}")
        if not chunks:
            print("WARNING: reference collection is empty; RAG cannot supply evidence.")
        if settings.demo_mode:
            print("WARNING: offline demo mode; external connections were not checked.")
            return 0
        prefix = settings.ai_provider.upper()
        if settings.provider_model.lower().startswith(("replace", "your-", "example")):
            print("WARNING: model setting appears to contain an example value.")
        stage, names = "model lookup", f"{prefix}_API_KEY, {prefix}_MODEL (or provider connectivity)"
        sdk = AsyncOpenAI if settings.ai_provider == "openai" else AsyncAnthropic
        base_url = "https://api.openai.com/v1" if settings.ai_provider == "openai" else "https://api.anthropic.com"
        async with sdk(
            api_key=getattr(settings, f"{settings.ai_provider}_api_key").get_secret_value(), base_url=base_url,
            timeout=settings.api_timeout_seconds, max_retries=0,
            http_client=httpx.AsyncClient(timeout=settings.api_timeout_seconds, trust_env=False),
        ) as client:
            lookup = getattr(getattr(client, "models", None), "retrieve", None)
            if lookup is None:
                print(f"WARNING: {settings.ai_provider} SDK has no model lookup; provider connectivity was not verified.")
            else:
                await lookup(settings.provider_model)
                print(f"OK: {settings.ai_provider} model lookup succeeded (read-only).")
        # Most incoming webhooks have no safe read-only authentication check.
        print("WARNING: webhook format validated only; delivery is intentionally not tested.")
        if ai_probe:
            stage, names = "AI probe", f"{prefix}_MODEL, {prefix}_API_KEY, MAX_OUTPUT_TOKENS"
            provider = create_ai(settings)
            try:
                await provider.generate("Summarize this synthetic support request for human review.", [])
            finally:
                await provider.close()
            print("OK: optional single billable AI probe completed.")
        return 0
    except SettingsError as error:
        print(f"ERROR: step=settings; check {', '.join(error.fields)}. Values are not shown.")
        return 1
    except Exception as error:
        if isinstance(error, (APIStatusError, anthropic.APIStatusError)):
            code = status_error_code(settings.ai_provider, error)
            names = {401: f"{prefix}_API_KEY", 403: f"{prefix}_API_KEY", 404: f"{prefix}_MODEL"}.get(error.status_code, names)
            if code == "provider_quota":
                names = f"{prefix}_API_KEY account billing/credits (provider_quota; the service owner must check billing)"
        elif isinstance(error, (APITimeoutError, anthropic.APITimeoutError)):
            names = "API_TIMEOUT_SECONDS (or provider connectivity)"
        elif isinstance(error, AIUnavailable) and error.code == "provider_quota":
            names = f"{prefix}_API_KEY account billing/credits (provider_quota; the service owner must check billing)"
        # Do not include exception text, input values, request URLs, or response bodies.
        print(f"ERROR: step={stage}; check {names}. Values are not shown.")
        return 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ai", "--openai", dest="ai_probe", action="store_true",
                        help="Allow one short billable probe using the selected provider (--openai is a legacy alias).")
    return asyncio.run(check(parser.parse_args(argv).ai_probe))


if __name__ == "__main__":
    raise SystemExit(main())
