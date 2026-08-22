from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class FragmentCreate(BaseModel):
    """Incoming raw context fragment."""

    content: str = Field(..., min_length=1, description="Raw text content")
    source: str = Field(default="cli", description="Source name (cli, webhook, mcp, ...)")
    external_id: str | None = Field(default=None, description="Idempotency key from source")
    content_type: str = Field(default="text/plain")
    metadata: dict[str, Any] = Field(default_factory=dict)
    captured_at: datetime | None = None


class FragmentResponse(BaseModel):
    id: UUID
    source_id: UUID
    external_id: str | None
    content_type: str
    raw_content: str
    metadata: dict[str, Any]
    captured_at: datetime
    ingested_at: datetime
    processing_status: str


class EntryResponse(BaseModel):
    id: UUID
    fragment_id: UUID | None
    title: str | None
    summary: str | None
    body: str
    tags: list[str]
    entities: list[dict[str, Any]]
    importance: float
    valid_from: datetime
    valid_until: datetime | None
    created_at: datetime
    similarity: float | None = None


class IngestResponse(BaseModel):
    fragment_id: UUID
    status: str = "queued"
    message: str = "Fragment accepted for processing"


class ContextQuery(BaseModel):
    query: str = Field(..., min_length=1)
    limit: int = Field(default=10, ge=1, le=100)
    min_importance: float = Field(default=0.0, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)
    since: datetime | None = None


class ContextSearchResult(BaseModel):
    entries: list[EntryResponse]
    total: int
    query: str
