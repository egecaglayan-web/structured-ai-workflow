import httpx
import pytest

from app import config


@pytest.fixture(autouse=True)
def isolated_configuration(monkeypatch, tmp_path):
    # Read only synthetic test .env files; never inherit an operator's configuration.
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.delenv("PYTHON_DOTENV_DISABLED", raising=False)
    for name in config.Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)


@pytest.fixture(autouse=True)
def no_external_http(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Unexpected external HTTP request in an offline test.")

    async def async_blocked(*args, **kwargs):
        blocked()

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", blocked)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", async_blocked)
