import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent


class SettingsError(ValueError):
    """Safe configuration diagnostics containing setting names only."""

    def __init__(self, fields):
        self.fields = tuple(sorted(set(fields)))
        super().__init__(f"Invalid settings: {', '.join(self.fields)}. Values are not shown.")


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True, validate_default=True)

    demo_mode: bool = True
    ai_provider: Literal["openai", "anthropic"] = "openai"
    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = ""
    anthropic_api_key: SecretStr = SecretStr("")
    anthropic_model: str = "claude-haiku-5-5"
    app_access_token: SecretStr = SecretStr("")
    owner_webhook_url: SecretStr = SecretStr("")
    api_timeout_seconds: float = Field(default=30, ge=1, le=90)
    max_output_tokens: int = Field(default=2000, ge=256, le=8000)
    requests_per_minute: int = Field(default=10, ge=1, le=120)
    cache_ttl_hours: int = Field(default=24, ge=1, le=168)
    database_path: Path = ROOT / "data/requests.sqlite3"
    reference_dir: Path = ROOT / "reference_docs"

    @property
    def provider_model(self) -> str:
        return self.openai_model if self.ai_provider == "openai" else self.anthropic_model

    @field_validator("openai_api_key", "openai_model", "anthropic_api_key", "anthropic_model",
                     "app_access_token", "owner_webhook_url")
    @classmethod
    def validate_live_setting(cls, value, info):
        if info.data.get("demo_mode", True):
            return value
        if info.field_name.startswith(("openai_", "anthropic_")):
            if not info.field_name.startswith(info.data.get("ai_provider", "openai") + "_"):
                return value
        raw = value.get_secret_value() if isinstance(value, SecretStr) else value
        if not raw.strip():
            raise ValueError("Required in live mode.")
        if info.field_name == "app_access_token":
            if len(raw) < 32:
                raise ValueError("Live access code must contain at least 32 characters.")
        if info.field_name == "owner_webhook_url":
            url = urlsplit(raw)
            if url.scheme != "https" or not url.hostname or url.username or url.password:
                raise ValueError("Live owner webhook must be an HTTPS URL without user info.")
        return value


def load_settings() -> Settings:
    try:
        load_dotenv(ROOT / ".env", override=False, interpolate=False, encoding="utf-8")
    except (OSError, UnicodeError):
        raise SettingsError(("ENV_FILE",)) from None
    values = {}
    for name in Settings.model_fields:
        raw = os.environ.get(name.upper())
        if raw is not None:
            values[name] = raw
    provider = values.get("ai_provider", "openai")
    if provider not in {"openai", "anthropic"}:
        raise SettingsError(("AI_PROVIDER",))
    required = (f"{provider.upper()}_API_KEY", f"{provider.upper()}_MODEL", "APP_ACCESS_TOKEN", "OWNER_WEBHOOK_URL")
    missing = False
    for name in required:
        value = values.get(name.lower(), Settings.model_fields[name.lower()].default)
        raw = value.get_secret_value() if isinstance(value, SecretStr) else value
        missing = missing or not str(raw).strip()
    raw_demo = os.environ.get("DEMO_MODE", "false").strip().lower()
    if raw_demo not in {"1", "true", "yes", "0", "false", "no"}:
        raise SettingsError(("DEMO_MODE",))
    requested_demo = raw_demo in {"1", "true", "yes"}
    values["demo_mode"] = requested_demo or missing
    try:
        return Settings(**values)
    except ValidationError as error:
        names = [str(item["loc"][0]).upper() for item in error.errors(include_input=False, include_context=False)
                 if item["loc"] and item["loc"][0] in Settings.model_fields]
        raise SettingsError(names or ("SETTINGS",)) from None
