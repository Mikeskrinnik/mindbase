import json
import uuid
from datetime import datetime, timezone

import redis.asyncio as redis
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from mindbase_shared.config import Settings
from mindbase_shared.models import (
    ContextQuery,
    ContextSearchResult,
    EntryResponse,
    FragmentCreate,
    FragmentResponse,
    IngestResponse,
)
from mindbase_api.db import Entry, Fragment, Source, check_db, get_session, get_source_by_name

settings = Settings()
app = FastAPI(
    title="Mindbase API",
    description="Unified context memory — ingest and query",
    version="0.1.0",
)

_redis: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> None:
    if x_api_key != settings.mindbase_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")


@app.get("/health")
async def health():
    db_ok = await check_db()
    redis_ok = False
    try:
        r = await get_redis()
        redis_ok = await r.ping()
    except Exception:
        pass

    status = "healthy" if db_ok and redis_ok else "degraded"
    return {"status": status, "database": db_ok, "redis": redis_ok}


@app.post("/v1/ingest", response_model=IngestResponse, dependencies=[Depends(verify_api_key)])
async def ingest(
    payload: FragmentCreate,
    session: AsyncSession = Depends(get_session),
):
    source = await get_source_by_name(session, payload.source)
    if not source:
        raise HTTPException(status_code=400, detail=f"Unknown source: {payload.source}")

    captured_at = payload.captured_at or datetime.now(timezone.utc)
    now = datetime.now(timezone.utc)

    if payload.external_id:
        existing = await session.execute(
            select(Fragment).where(
                Fragment.source_id == source.id,
                Fragment.external_id == payload.external_id,
            )
        )
        if row := existing.scalar_one_or_none():
            return IngestResponse(
                fragment_id=row.id,
                status="duplicate",
                message="Fragment already exists (idempotent)",
            )

    fragment = Fragment(
        id=uuid.uuid4(),
        source_id=source.id,
        external_id=payload.external_id,
        content_type=payload.content_type,
        raw_content=payload.content,
        metadata_=payload.metadata,
        captured_at=captured_at,
        ingested_at=now,
        processing_status="pending",
    )
    session.add(fragment)
    await session.commit()

    r = await get_redis()
    await r.xadd(
        settings.stream_key,
        {
            "fragment_id": str(fragment.id),
            "source": payload.source,
            "captured_at": captured_at.isoformat(),
        },
    )

    return IngestResponse(fragment_id=fragment.id)


@app.get("/v1/fragments/{fragment_id}", response_model=FragmentResponse, dependencies=[Depends(verify_api_key)])
async def get_fragment(fragment_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Fragment).where(Fragment.id == fragment_id))
    fragment = result.scalar_one_or_none()
    if not fragment:
        raise HTTPException(status_code=404, detail="Fragment not found")
    return FragmentResponse(
        id=fragment.id,
        source_id=fragment.source_id,
        external_id=fragment.external_id,
        content_type=fragment.content_type,
        raw_content=fragment.raw_content,
        metadata=fragment.metadata_,
        captured_at=fragment.captured_at,
        ingested_at=fragment.ingested_at,
        processing_status=fragment.processing_status,
    )


@app.post("/v1/search", response_model=ContextSearchResult, dependencies=[Depends(verify_api_key)])
async def search_context(
    query: ContextQuery,
    session: AsyncSession = Depends(get_session),
):
    """Semantic + keyword hybrid search. Falls back to full-text when no embedding key."""
    sql_parts = [
        "SELECT id, fragment_id, title, summary, body, tags, entities, importance,",
        "valid_from, valid_until, created_at, NULL::float AS similarity",
        "FROM entries WHERE 1=1",
    ]
    params: dict = {"limit": query.limit}

    if query.min_importance > 0:
        sql_parts.append("AND importance >= :min_importance")
        params["min_importance"] = query.min_importance

    if query.since:
        sql_parts.append("AND valid_from >= :since")
        params["since"] = query.since

    if query.tags:
        sql_parts.append("AND tags && :tags")
        params["tags"] = query.tags

    sql_parts.append("AND body ILIKE :pattern")
    params["pattern"] = f"%{query.query}%"

    sql_parts.append("ORDER BY valid_from DESC LIMIT :limit")
    sql = " ".join(sql_parts)

    result = await session.execute(text(sql), params)
    rows = result.fetchall()

    entries = [
        EntryResponse(
            id=row.id,
            fragment_id=row.fragment_id,
            title=row.title,
            summary=row.summary,
            body=row.body,
            tags=list(row.tags or []),
            entities=row.entities or [],
            importance=row.importance,
            valid_from=row.valid_from,
            valid_until=row.valid_until,
            created_at=row.created_at,
            similarity=row.similarity,
        )
        for row in rows
    ]

    return ContextSearchResult(entries=entries, total=len(entries), query=query.query)


@app.get("/v1/context/recent", response_model=ContextSearchResult, dependencies=[Depends(verify_api_key)])
async def recent_context(
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Entry).order_by(Entry.valid_from.desc()).limit(limit)
    )
    entries_db = result.scalars().all()
    entries = [
        EntryResponse(
            id=e.id,
            fragment_id=e.fragment_id,
            title=e.title,
            summary=e.summary,
            body=e.body,
            tags=list(e.tags or []),
            entities=e.entities or [],
            importance=e.importance,
            valid_from=e.valid_from,
            valid_until=e.valid_until,
            created_at=e.created_at,
        )
        for e in entries_db
    ]
    return ContextSearchResult(entries=entries, total=len(entries), query="recent")


@app.get("/v1/context/summary", dependencies=[Depends(verify_api_key)])
async def context_summary(session: AsyncSession = Depends(get_session)):
    """Compact context bundle for AI models — last N entries as markdown."""
    result = await session.execute(
        select(Entry).order_by(Entry.valid_from.desc()).limit(30)
    )
    entries = result.scalars().all()

    lines = ["# Mindbase Context Summary", ""]
    for e in entries:
        ts = e.valid_from.strftime("%Y-%m-%d %H:%M")
        title = e.title or e.body[:80]
        lines.append(f"## [{ts}] {title}")
        if e.summary:
            lines.append(e.summary)
        else:
            lines.append(e.body[:500])
        if e.tags:
            lines.append(f"*Tags: {', '.join(e.tags)}*")
        lines.append("")

    return {"format": "markdown", "content": "\n".join(lines), "entry_count": len(entries)}


@app.get("/v1/export/entries", dependencies=[Depends(verify_api_key)])
async def export_entries(
    since: datetime | None = Query(default=None, description="ISO timestamp for incremental export"),
    limit: int = Query(default=500, ge=1, le=5000),
    session: AsyncSession = Depends(get_session),
):
    """Export structured entries for iCloud mirror / offline sync."""
    sql = """
        SELECT e.id, e.fragment_id, e.title, e.summary, e.body, e.tags, e.entities,
               e.importance, e.valid_from, e.valid_until, e.created_at,
               COALESCE(s.name, 'unknown') AS source
        FROM entries e
        LEFT JOIN fragments f ON f.id = e.fragment_id
        LEFT JOIN sources s ON s.id = f.source_id
        WHERE 1=1
    """
    params: dict = {"limit": limit}

    if since:
        sql += " AND e.updated_at >= :since"
        params["since"] = since

    sql += " ORDER BY e.updated_at ASC LIMIT :limit"

    result = await session.execute(text(sql), params)
    rows = result.fetchall()

    entries = [
        {
            "id": str(row.id),
            "fragment_id": str(row.fragment_id) if row.fragment_id else None,
            "title": row.title,
            "summary": row.summary,
            "body": row.body,
            "tags": list(row.tags or []),
            "entities": row.entities or [],
            "importance": row.importance,
            "valid_from": row.valid_from.isoformat() if row.valid_from else None,
            "valid_until": row.valid_until.isoformat() if row.valid_until else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "source": row.source,
        }
        for row in rows
    ]

    return {"entries": entries, "count": len(entries), "since": since.isoformat() if since else None}
