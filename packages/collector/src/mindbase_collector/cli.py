"""Mindbase CLI collector."""

import json
import sys
import uuid
from datetime import datetime, timezone

import click
import httpx
from pydantic_settings import BaseSettings, SettingsConfigDict


class CLISettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mindbase_api_url: str = "http://localhost:8080"
    mindbase_api_key: str = "dev-key-change-me"


settings = CLISettings()


def ingest(content: str, source: str = "cli", metadata: dict | None = None, external_id: str | None = None) -> dict:
    payload = {
        "content": content,
        "source": source,
        "metadata": metadata or {},
        "external_id": external_id,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    with httpx.Client(timeout=15) as client:
        resp = client.post(
            f"{settings.mindbase_api_url.rstrip('/')}/v1/ingest",
            headers={"X-API-Key": settings.mindbase_api_key},
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()


@click.group()
def main():
    """Mindbase — capture context from anywhere."""
    pass


@main.command()
@click.argument("text")
@click.option("--tag", "-t", multiple=True, help="Add tags")
def note(text: str, tag: tuple):
    """Quickly save a thought."""
    meta = {"tags": list(tag)} if tag else {}
    result = ingest(text, metadata=meta)
    click.echo(f"✓ Saved ({result['fragment_id']})")


@main.command()
@click.option("--file", "-f", type=click.Path(exists=True), help="Read from file")
def pipe(file: str | None):
    """Read from stdin or file and save silently."""
    content = open(file).read() if file else sys.stdin.read()
    if not content.strip():
        click.echo("Nothing to capture", err=True)
        sys.exit(1)
    external_id = f"pipe-{uuid.uuid4().hex}"
    result = ingest(content.strip(), external_id=external_id)
    click.echo(json.dumps(result))


@main.command()
@click.argument("query")
@click.option("--limit", "-n", default=10)
def search(query: str, limit: int):
    """Search your context memory."""
    with httpx.Client(timeout=15) as client:
        resp = client.post(
            f"{settings.mindbase_api_url.rstrip('/')}/v1/search",
            headers={"X-API-Key": settings.mindbase_api_key},
            json={"query": query, "limit": limit},
        )
        resp.raise_for_status()
        data = resp.json()
        for entry in data["entries"]:
            ts = entry["valid_from"][:16].replace("T", " ")
            title = entry.get("title") or entry["body"][:60]
            click.echo(f"[{ts}] {title}")


@main.command()
def summary():
    """Print context summary (for shell scripts / AI prompts)."""
    with httpx.Client(timeout=15) as client:
        resp = client.get(
            f"{settings.mindbase_api_url.rstrip('/')}/v1/context/summary",
            headers={"X-API-Key": settings.mindbase_api_key},
        )
        resp.raise_for_status()
        click.echo(resp.json()["content"])


if __name__ == "__main__":
    main()
