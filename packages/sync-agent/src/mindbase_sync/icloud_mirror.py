"""Mirror Mindbase entries to iCloud Drive as markdown."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from mindbase_shared.icloud import entry_file_path, load_sync_state, save_sync_state, write_index
from mindbase_shared.markdown import entry_to_markdown

from mindbase_sync.client import MindbaseClient

logger = logging.getLogger("mindbase-sync.icloud")


def mirror_entries_to_icloud(icloud_root, client: MindbaseClient) -> int:
    """Pull entries from API and write markdown files to iCloud. Returns count written."""
    state = load_sync_state(icloud_root)
    since = None
    if state.get("last_pull"):
        try:
            since = datetime.fromisoformat(state["last_pull"])
        except ValueError:
            pass

    entries = client.export_entries(since=since)
    written = 0
    index_meta = []

    for entry in entries:
        entry_id = str(entry["id"])
        title = entry.get("title")
        body = entry.get("body", "")
        tags = entry.get("tags", [])
        captured_at = entry.get("valid_from") or entry.get("created_at")

        md = entry_to_markdown(
            entry_id=entry_id,
            title=title,
            body=body,
            tags=tags,
            source=entry.get("source", "mindbase"),
            captured_at=captured_at,
            importance=entry.get("importance"),
        )

        out_path = entry_file_path(icloud_root, entry_id, title)
        if out_path.exists():
            existing = out_path.read_text(encoding="utf-8")
            if existing == md:
                continue

        out_path.write_text(md, encoding="utf-8")
        written += 1
        logger.info("Mirrored entry %s → %s", entry_id, out_path.name)

        index_meta.append({
            "id": entry_id,
            "title": title,
            "tags": tags,
            "captured_at": captured_at,
            "path": str(out_path.relative_to(icloud_root)),
        })

    if index_meta:
        write_index(icloud_root, index_meta)

    state["last_pull"] = datetime.now(timezone.utc).isoformat()
    save_sync_state(icloud_root, state)
    return written
