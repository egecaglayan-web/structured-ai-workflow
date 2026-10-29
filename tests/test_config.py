import asyncio
import warnings
from getpass import GetPassWarning

import httpx
import pytest
from dotenv import dotenv_values
from openai import NotFoundError

from app import check as check_module, set_secret
from app.config import Settings, SettingsError, load_settings


def test_project_dotenv_loads_without_overriding_environment(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("REQUESTS_PER_MINUTE=5\nOPENAI_API_KEY='synthetic-${UNCHANGED}'\n", encoding="utf-8")
    monkeypatch.setenv("REQUESTS_PER_MINUTE", "7")
    assert load_settings().requests_per_minute == 7
    assert load_settings().openai_api_key.get_secret_value() == "synthetic-${UNCHANGED}"


@pytest.mark.parametrize("values,expected", [
    ({"API_TIMEOUT_SECONDS": "bad-private-value"}, "API_TIMEOUT_SECONDS"),
    ({"REQUESTS_PER_MINUTE": "0"}, "REQUESTS_PER_MINUTE"),
    ({"DEMO_MODE": "typo-private-value"}, "DEMO_MODE"),
    ({"OPENAI_API_KEY": "private-sentinel", "OPENAI_MODEL": "model", "APP_ACCESS_TOKEN": "short-private",
      "OWNER_WEBHOOK_URL": "https://example.invalid/notify"}, "APP_ACCESS_TOKEN"),
    ({"OPENAI_API_KEY": "private-sentinel", "OPENAI_MODEL": "model", "APP_ACCESS_TOKEN": "x" * 32,
      "OWNER_WEBHOOK_URL": "http://example.invalid/private"}, "OWNER_WEBHOOK_URL"),
])
def test_setting_diagnostics_name_fields_and_never_values(monkeypatch, capsys, values, expected):
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    with pytest.raises(SettingsError) as error:
        load_settings()
    assert expected in str(error.value)
    assert asyncio.run(check_module.check()) == 1
    output = capsys.readouterr().out
    assert "step=settings" in output and expected in output
    for value in values.values():
        if "private" in value:
            assert value not in output + str(error.value)


def test_reference_diagnostic_names_step_and_setting(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(check_module, "load_settings", lambda: Settings(reference_dir=tmp_path / "missing-private-path"))
    assert asyncio.run(check_module.check()) == 1
    output = capsys.readouterr().out
    assert "step=reference docs" in output and "REFERENCE_DIR" in output
    assert "missing-private-path" not in output


def test_model_lookup_diagnostic_names_step_and_setting(monkeypatch, capsys):
    settings = Settings(demo_mode=False, openai_api_key="private-sentinel", openai_model="private-model",
                        app_access_token="x" * 32, owner_webhook_url="https://example.invalid/notify")
    class Client:
        models = None
        def __init__(self, **kwargs):
            self.models = self
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            await self.http.aclose()
        async def retrieve(self, model):
            response = httpx.Response(404, request=httpx.Request("GET", "https://example.invalid/private-model"))
            raise NotFoundError("private-sentinel", response=response, body=None)
    def factory(**kwargs):
        client = Client()
        client.http = kwargs["http_client"]
        return client
    monkeypatch.setattr(check_module, "load_settings", lambda: settings)
    monkeypatch.setattr(check_module, "AsyncOpenAI", factory)
    assert asyncio.run(check_module.check()) == 1
    output = capsys.readouterr().out
    assert "step=model lookup" in output and "OPENAI_MODEL" in output
    assert "private-sentinel" not in output and "private-model" not in output


@pytest.mark.parametrize("name", ["OPENAI_API_KEY", "ANTHROPIC_API_KEY"])
def test_secret_helper_preserves_other_lines_and_never_prints_value(tmp_path, monkeypatch, capsys, name):
    path = tmp_path / ".env"
    other_lines = "# Keep this comment\nDEMO_MODE=true\n\nOTHER='unchanged'\n"
    path.write_text(other_lines + f"{name}='old-synthetic-value'\n", encoding="utf-8")
    value = "synthetic-value-with-'quotes'-and-${literal}"
    monkeypatch.setattr(set_secret, "getpass", lambda prompt: value)
    assert set_secret.main([name], path=path) == 0
    assert path.read_text(encoding="utf-8").startswith(other_lines)
    assert dotenv_values(path, interpolate=False)[name] == value
    assert value not in capsys.readouterr().out


@pytest.mark.parametrize("values", [("first", "second"), ("", ""), ("line\nbreak", "line\nbreak")])
def test_secret_helper_rejects_invalid_values_without_creating_file(tmp_path, monkeypatch, capsys, values):
    answers = iter(values)
    monkeypatch.setattr(set_secret, "getpass", lambda prompt: next(answers))
    path = tmp_path / ".env"
    assert set_secret.main(["OPENAI_API_KEY"], path=path) == 1
    assert not path.exists()
    output = capsys.readouterr().out
    assert all(value not in output for value in values if value)


def test_secret_helper_refuses_echoing_fallback(tmp_path, monkeypatch):
    def no_terminal(prompt):
        warnings.warn("Cannot hide input", GetPassWarning)
        pytest.fail("Must stop before fallback reads input")
    monkeypatch.setattr(set_secret, "getpass", no_terminal)
    path = tmp_path / ".env"
    assert set_secret.main(["OPENAI_API_KEY"], path=path) == 1
    assert not path.exists()
