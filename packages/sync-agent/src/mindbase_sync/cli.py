"""CLI for Obsidian + iCloud sync."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

from mindbase_shared.config import Settings
from mindbase_shared.icloud import icloud_drive_root, resolve_mindbase_root

from mindbase_sync.client import MindbaseClient
from mindbase_sync.icloud_mirror import mirror_entries_to_icloud
from mindbase_sync.obsidian import sync_vault_to_mindbase, watch_vault

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("mindbase-sync")
settings = Settings()


def _client() -> MindbaseClient:
    return MindbaseClient(settings.mindbase_api_url, settings.mindbase_api_key)


def _icloud_root(custom: str | None) -> Path:
    return resolve_mindbase_root(custom or settings.icloud_mindbase_path or None)


def _vault_path(custom: str | None) -> Path:
    path_str = custom or settings.obsidian_vault_path
    if not path_str:
        click.echo("Error: set OBSIDIAN_VAULT_PATH or pass --vault", err=True)
        sys.exit(1)
    path = Path(path_str).expanduser()
    if not path.is_dir():
        click.echo(f"Error: vault not found: {path}", err=True)
        sys.exit(1)
    return path


@click.group()
def main():
    """Mindbase sync — Obsidian vault ↔ API ↔ iCloud Drive."""
    pass


@main.command()
@click.option("--vault", type=click.Path(exists=True), help="Obsidian vault path")
@click.option("--icloud", "icloud_path", type=click.Path(), help="iCloud Mindbase folder")
def status(vault: str | None, icloud_path: str | None):
    """Show sync status and paths."""
    root = _icloud_root(icloud_path)
    icloud = icloud_drive_root()
    client = _client()

    click.echo("Mindbase Sync Status")
    click.echo("─" * 40)
    click.echo(f"API:           {settings.mindbase_api_url} ({'ok' if client.health() else 'unreachable'})")
    click.echo(f"iCloud Drive:  {'found' if icloud else 'not available (non-macOS?)'}")
    click.echo(f"Mindbase root: {root}")
    if vault or settings.obsidian_vault_path:
        v = _vault_path(vault)
        click.echo(f"Obsidian vault: {v}")
    else:
        click.echo("Obsidian vault: not configured")


@main.command()
@click.option("--vault", type=click.Path(exists=True), help="Obsidian vault path")
@click.option("--icloud", "icloud_path", type=click.Path(), help="iCloud Mindbase folder")
def push(vault: str | None, icloud_path: str | None):
    """Push Obsidian notes → Mindbase API."""
    root = _icloud_root(icloud_path)
    v = _vault_path(vault)
    count = sync_vault_to_mindbase(v, root, _client())
    click.echo(f"✓ Pushed {count} changed note(s) to Mindbase")


@main.command()
@click.option("--icloud", "icloud_path", type=click.Path(), help="iCloud Mindbase folder")
def pull(icloud_path: str | None):
    """Pull Mindbase entries → iCloud Drive (markdown)."""
    root = _icloud_root(icloud_path)
    count = mirror_entries_to_icloud(root, _client())
    click.echo(f"✓ Mirrored {count} entry(ies) to iCloud: {root}")


@main.command()
@click.option("--vault", type=click.Path(exists=True), help="Obsidian vault path")
@click.option("--icloud", "icloud_path", type=click.Path(), help="iCloud Mindbase folder")
@click.option("--interval", default=None, type=int, help="Poll interval seconds")
def watch(vault: str | None, icloud_path: str | None, interval: int | None):
    """Run continuous sync: Obsidian → API → iCloud mirror."""
    root = _icloud_root(icloud_path)
    v = _vault_path(vault)
    client = _client()
    poll = interval or settings.sync_poll_interval_sec

    click.echo(f"Starting sync agent (poll every {poll}s)")
    click.echo(f"  Vault:  {v}")
    click.echo(f"  iCloud: {root}")
    click.echo(f"  API:    {settings.mindbase_api_url}")
    click.echo("Press Ctrl+C to stop")

    # Initial full sync
    pushed = sync_vault_to_mindbase(v, root, client)
    pulled = mirror_entries_to_icloud(root, client)
    click.echo(f"Initial sync: pushed {pushed}, mirrored {pulled}")

    watch_vault(v, root, client, poll_interval=poll)


@main.command()
@click.option("--icloud", "icloud_path", type=click.Path(), help="iCloud Mindbase folder")
def init(icloud_path: str | None):
    """Initialize iCloud Mindbase folder structure."""
    root = _icloud_root(icloud_path)
    readme = root / "README.md"
    readme.write_text(
        """# Mindbase (iCloud)

Эта папка синхронизируется через iCloud Drive на все ваши устройства.

## Структура

- `entries/` — структурированные записи из Mindbase (markdown)
- `inbox/` — новые заметки, которые можно открыть в Obsidian
- `obsidian-sync/` — состояние синхронизации (не трогать)
- `index.json` — офлайн-индекс для быстрого поиска

## Настройка Obsidian

1. В Obsidian: Settings → Files → «Default location for new notes» → `inbox`
2. Или добавьте эту папку как vault: `entries/` и `inbox/`

## Синхронизация

На Mac запустите агент:
```
mindbase-sync watch --vault ~/Documents/MyVault
```
""",
        encoding="utf-8",
    )
    click.echo(f"✓ Initialized iCloud folder: {root}")


if __name__ == "__main__":
    main()
