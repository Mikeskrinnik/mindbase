"""iCloud Drive storage helpers.

macOS:
  ~/Library/Mobile Documents/com~apple~CloudDocs/

Windows (iCloud for Windows):
  ~/iCloudDrive/
  ~/Apple iCloud/iCloudDrive/
"""

from __future__ import annotations

import json
import os
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ICLOUD_CONTAINER = "com~apple~CloudDocs"
DEFAULT_MINDBASE_FOLDER = "Mindbase"

# Common iCloud for Windows install paths (varies by app version)
WINDOWS_ICLOUD_CANDIDATES = (
    "iCloudDrive",
    "Apple iCloud/iCloudDrive",
    "iCloud Drive",
)


def icloud_drive_root() -> Path | None:
    """Return iCloud Drive root if available on this machine."""
    system = platform.system()

    if system == "Darwin":
        root = Path.home() / "Library" / "Mobile Documents" / ICLOUD_CONTAINER
        return root if root.is_dir() else None

    if system == "Windows":
        home = Path.home()
        for candidate in WINDOWS_ICLOUD_CANDIDATES:
            root = home / candidate
            if root.is_dir():
                return root
        # Some installs use OneDrive-style path under AppData (rare)
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            legacy = Path(appdata) / "Apple Inc" / "Apple iCloud Drive"
            if legacy.is_dir():
                return legacy
        return None

    return None


def resolve_mindbase_root(custom_path: str | None = None) -> Path:
    """Resolve Mindbase iCloud folder, creating it if needed."""
    if custom_path:
        path = Path(custom_path).expanduser()
    else:
        icloud = icloud_drive_root()
        if icloud:
            path = icloud / DEFAULT_MINDBASE_FOLDER
        else:
            # Dev / Linux fallback — mimic iCloud layout locally
            path = Path.home() / "Mindbase-iCloud"

    path.mkdir(parents=True, exist_ok=True)
    for sub in ("entries", "inbox", "obsidian-sync", "attachments"):
        (path / sub).mkdir(exist_ok=True)
    return path


def sync_state_path(root: Path) -> Path:
    return root / "obsidian-sync" / "state.json"


def load_sync_state(root: Path) -> dict[str, Any]:
    path = sync_state_path(root)
    if not path.exists():
        return {"files": {}, "last_pull": None, "last_push": None}
    return json.loads(path.read_text(encoding="utf-8"))


def save_sync_state(root: Path, state: dict[str, Any]) -> None:
    path = sync_state_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def entry_file_path(root: Path, entry_id: str, title: str | None = None) -> Path:
    """Stable path for an entry markdown file in iCloud."""
    safe_title = _slugify(title or "untitled")[:60]
    return root / "entries" / f"{entry_id}_{safe_title}.md"


def obsidian_inbox_path(root: Path, filename: str) -> Path:
    return root / "inbox" / filename


def _slugify(text: str) -> str:
    import re

    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-") or "note"


def write_index(root: Path, entries_meta: list[dict[str, Any]]) -> Path:
    """Write lightweight search index to iCloud for offline access."""
    index_path = root / "index.json"
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(entries_meta),
        "entries": entries_meta,
    }
    index_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return index_path
