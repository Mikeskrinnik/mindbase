import asyncio
import logging
import re
import uuid
from datetime import datetime, timezone

import httpx
import redis.asyncio as redis
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mindbase_shared.config import Settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("mindbase-worker")

settings = Settings()
engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

TAG_PATTERNS = [
    (r"#(\w+)", "hashtag"),
    (r"@(\w+)", "mention"),
]

ENTITY_PATTERNS = [
    (r"\b(?:https?://[^\s]+)\b", "url"),
    (r"\b[\w.-]+@[\w.-]+\.\w+\b", "email"),
    (r"\b\d{1,2}[./]\d{1,2}[./]\d{2,4}\b", "date"),
]


def extract_tags(content: str) -> list[str]:
    tags = set()
    for pattern, _ in TAG_PATTERNS:
        tags.update(re.findall(pattern, content, re.IGNORECASE))
    return sorted(tags)


def extract_entities(content: str) -> list[dict]:
    entities = []
    for pattern, kind in ENTITY_PATTERNS:
        for match in re.finditer(pattern, content):
            entities.append({"kind": kind, "value": match.group(0), "start": match.start()})
    return entities


def generate_title(body: str) -> str:
    first_line = body.strip().split("\n")[0]
    return first_line[:120] + ("..." if len(first_line) > 120 else "")


def generate_summary(body: str) -> str:
    text_clean = " ".join(body.split())
    return text_clean[:300] + ("..." if len(text_clean) > 300 else "")


def score_importance(body: str, tags: list[str], entities: list) -> float:
    score = 0.4
    score += min(len(body) / 2000, 0.2)
    score += min(len(tags) * 0.05, 0.15)
    score += min(len(entities) * 0.03, 0.15)
    if "?" in body:
        score += 0.05
    return min(score, 1.0)


async def fetch_embedding(text: str) -> list[float] | None:
    if not settings.embedding_api_key:
        return None
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{settings.embedding_api_url}/embeddings",
                headers={"Authorization": f"Bearer {settings.embedding_api_key}"},
                json={"model": settings.embedding_model, "input": text[:8000]},
            )
            resp.raise_for_status()
            return resp.json()["data"][0]["embedding"]
    except Exception as e:
        logger.warning("Embedding fetch failed: %s", e)
        return None


async def process_fragment(session: AsyncSession, fragment_id: uuid.UUID) -> None:
    result = await session.execute(
        text(
            "SELECT id, raw_content, metadata FROM fragments WHERE id = :id AND processing_status = 'pending'"
        ),
        {"id": str(fragment_id)},
    )
    row = result.fetchone()
    if not row:
        return

    await session.execute(
        text("UPDATE fragments SET processing_status = 'processing' WHERE id = :id"),
        {"id": str(fragment_id)},
    )
    await session.commit()

    body = row.raw_content
    tags = extract_tags(body)
    entities = extract_entities(body)
    importance = score_importance(body, tags, entities)
    embedding = await fetch_embedding(body)

    entry_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    if embedding:
        await session.execute(
            text("""
                INSERT INTO entries (id, fragment_id, title, summary, body, tags, entities,
                                     importance, embedding, valid_from, created_at, updated_at)
                VALUES (:id, :fragment_id, :title, :summary, :body, :tags, :entities,
                        :importance, :embedding::vector, :now, :now, :now)
            """),
            {
                "id": str(entry_id),
                "fragment_id": str(fragment_id),
                "title": generate_title(body),
                "summary": generate_summary(body),
                "body": body,
                "tags": tags,
                "entities": entities,
                "importance": importance,
                "embedding": str(embedding),
                "now": now,
            },
        )
    else:
        await session.execute(
            text("""
                INSERT INTO entries (id, fragment_id, title, summary, body, tags, entities,
                                     importance, valid_from, created_at, updated_at)
                VALUES (:id, :fragment_id, :title, :summary, :body, :tags, :entities,
                        :importance, :now, :now, :now)
            """),
            {
                "id": str(entry_id),
                "fragment_id": str(fragment_id),
                "title": generate_title(body),
                "summary": generate_summary(body),
                "body": body,
                "tags": tags,
                "entities": entities,
                "importance": importance,
                "now": now,
            },
        )

    await session.execute(
        text("UPDATE fragments SET processing_status = 'done' WHERE id = :id"),
        {"id": str(fragment_id)},
    )
    await session.commit()
    logger.info("Processed fragment %s → entry %s", fragment_id, entry_id)


async def record_failure(session: AsyncSession, fragment_id: uuid.UUID, error: str) -> None:
    await session.execute(
        text("""
            UPDATE fragments SET processing_status = 'failed' WHERE id = :id;
            INSERT INTO failed_jobs (fragment_id, error, attempts) VALUES (:id, :error, 1);
        """),
        {"id": str(fragment_id), "error": error[:2000]},
    )
    await session.commit()


async def ensure_consumer_group(r: redis.Redis) -> None:
    try:
        await r.xgroup_create(settings.stream_key, settings.consumer_group, id="0", mkstream=True)
        logger.info("Created consumer group %s", settings.consumer_group)
    except redis.ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise


async def run_worker() -> None:
    r = redis.from_url(settings.redis_url, decode_responses=True)
    await ensure_consumer_group(r)
    consumer_name = f"worker-{uuid.uuid4().hex[:8]}"
    logger.info("Worker %s started", consumer_name)

    while True:
        try:
            messages = await r.xreadgroup(
                settings.consumer_group,
                consumer_name,
                {settings.stream_key: ">"},
                count=settings.worker_batch_size,
                block=settings.worker_poll_interval_ms,
            )

            if not messages:
                continue

            for _stream, entries in messages:
                for msg_id, fields in entries:
                    fragment_id = uuid.UUID(fields["fragment_id"])
                    try:
                        async with SessionLocal() as session:
                            await process_fragment(session, fragment_id)
                        await r.xack(settings.stream_key, settings.consumer_group, msg_id)
                    except Exception as e:
                        logger.exception("Failed to process %s", fragment_id)
                        async with SessionLocal() as session:
                            await record_failure(session, fragment_id, str(e))
                        await r.xack(settings.stream_key, settings.consumer_group, msg_id)

        except Exception:
            logger.exception("Worker loop error")
            await asyncio.sleep(2)


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
