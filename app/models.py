from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProcessRequest(StrictModel):
    request_id: UUID
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=8000)]
    use_references: bool = True
    website: str = Field(default="", max_length=200)  # Honeypot; real users leave this empty.


class ProviderBrief(StrictModel):
    """Portable provider schema; enforce size limits locally after generation."""

    summary: str
    category: Literal["support", "sales", "feedback", "other"]
    next_steps: list[str]
    source_ids: list[str]


class Brief(StrictModel):
    summary: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1500)]
    category: Literal["support", "sales", "feedback", "other"]
    next_steps: list[ShortText] = Field(min_length=1, max_length=5)
    source_ids: list[str] = Field(max_length=3)


class Citation(StrictModel):
    source_id: str
    document: str
    excerpt: str


class ProcessResult(StrictModel):
    request_id: UUID
    mode: Literal["demo", "live", "fallback"]
    provider: Literal["openai", "anthropic", "demo"]
    brief: Brief
    needs_human_review: bool = True
    citations: list[Citation]
    warning: str | None = None
    error_code: str | None = None
