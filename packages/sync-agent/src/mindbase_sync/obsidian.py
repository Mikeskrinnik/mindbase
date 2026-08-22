"""Obsidian vault → Mindbase ingest."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from mindbase_shared.icloud import load_sync_state, save_sync_state
from mindbase_shared.markdown import obsidian_note_to_ingest

from mindbase_sync.client import MindbaseClient

logger = logging.getLogger("mindbase-sync.obsidian")

IGNORE_DIRS = {".obsidian", ".trash", ".git", "node_modules"}
IGNORE_FILES = {".DS_Store"}


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scan_vault(vault_path: Path) -> list[Path]:
    notes = []
    for path in vault_path.rglob("*.md"):
        if any(part in IGNORE_DIRS for part in path.parts):
            continue
        if path.name in IGNORE_FILES:
            continue
        notes.append(path)
    return notes


def sync_vault_to_mindbase(
    vault_path: Path,
    icloud_root: Path,
    client: MindbaseClient,
) -> int:
    """Push changed Obsidian notes to Mindbase. Returns count of synced files."""
    state = load_sync_state(icloud_root)
    files_state: dict = state.setdefault("files", {})
    synced = 0

    for note_path in scan_vault(vault_path):
        rel = str(note_path.relative_to(vault_path))
        try:
            content = note_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            logger.warning("Skipping non-utf8 file: %s", rel)
            continue

        h = hashlib.sha256(content.encode()).hexdigest()
        prev = files_state.get(rel, {})
        if prev.get("hash") == h:
            continue

        payload = obsidian_note_to_ingest(rel, content)
        result = client.ingest(payload)
        files_state[rel] = {
            "hash": h,
            "fragment_id": result.get("fragment_id"),
            "synced_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        }
        synced += 1
        logger.info("Synced %s → %s", rel, result.get("fragment_id"))

    state["last_push"] = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
    save_sync_state(icloud_root, state)
    return synced


def watch_vault(vault_path: Path, icloud_root: Path, client: MindbaseClient, poll_interval: int = 30) -> None:
    """Watch Obsidian vault for changes using watchdog."""
    import time

    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    class Handler(FileSystemEventHandler):
        def on_any_event(self, event):
            if event.is_directory:
                return
            if not str(event.src_path).endswith(".md"):
                return
            logger.debug("Change detected: %s", event.src_path)
            try:
                sync_vault_to_mindbase(vault_path, icloud_root, client)
            except Exception:
                logger.exception("Sync failed after change")

    handler = Handler()
    observer = Observer()
    observer.schedule(handler, str(vault_path), recursive=True)
    observer.start()
    logger.info("Watching Obsidian vault: %s", vault_path)

    try:
        while True:
            time.sleep(poll_interval)
            sync_vault_to_mindbase(vault_path, icloud_root, client)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
