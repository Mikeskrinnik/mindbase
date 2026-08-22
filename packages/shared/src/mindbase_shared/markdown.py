"""Markdown + YAML frontmatter utilities for Obsidian / iCloud compatibility."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any


FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Split YAML frontmatter and body. Returns ({}, full_content) if no frontmatter."""
    match = FRONTMATTER_RE.match(content.strip())
    if not match:
        return {}, content

    meta: dict[str, Any] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if value.startswith("[") and value.endswith("]"):
            meta[key] = [v.strip().strip('"').strip("'") for v in value[1:-1].split(",") if v.strip()]
        else:
            meta[key] = value
    return meta, match.group(2).strip()


def build_frontmatter(meta: dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in meta.items():
        if isinstance(value, list):
            inner = ", ".join(f'"{v}"' for v in value)
            lines.append(f"{key}: [{inner}]")
        elif isinstance(value, datetime):
            lines.append(f'{key}: "{value.isoformat()}"')
        else:
            escaped = str(value).replace('"', '\\"')
            lines.append(f'{key}: "{escaped}"')
    lines.append("---")
    return "\n".join(lines)


def entry_to_markdown(
    *,
    entry_id: str,
    title: str | None,
    body: str,
    tags: list[str] | None = None,
    source: str = "mindbase",
    captured_at: datetime | str | None = None,
    importance: float | None = None,
    obsidian_uri: str | None = None,
) -> str:
    """Render a Mindbase entry as Obsidian-compatible markdown."""
    meta: dict[str, Any] = {
        "id": entry_id,
        "source": source,
        "tags": tags or [],
    }
    if title:
        meta["title"] = title
    if captured_at:
        meta["captured_at"] = captured_at if isinstance(captured_at, str) else captured_at.isoformat()
    if importance is not None:
        meta["importance"] = importance
    if obsidian_uri:
        meta["obsidian_uri"] = obsidian_uri

    fm = build_frontmatter(meta)
    heading = f"# {title}\n\n" if title and not body.startswith("#") else ""
    return f"{fm}\n\n{heading}{body}\n"


def obsidian_note_to_ingest(path: str, content: str) -> dict[str, Any]:
    """Convert an Obsidian note file into an ingest payload."""
    meta, body = parse_frontmatter(content)
    tags = meta.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",")]

    # Obsidian inline tags
    inline_tags = re.findall(r"#([\w/-]+)", body)
    all_tags = sorted(set(list(tags) + inline_tags))

    return {
        "content": body or content,
        "source": "obsidian",
        "external_id": f"obsidian:{path}",
        "content_type": "text/markdown",
        "metadata": {
            "obsidian_path": path,
            "title": meta.get("title") or _title_from_path(path),
            "tags": all_tags,
            "frontmatter": meta,
        },
    }


def _title_from_path(path: str) -> str:
    from pathlib import Path

    return Path(path).stem.replace("-", " ").replace("_", " ")
