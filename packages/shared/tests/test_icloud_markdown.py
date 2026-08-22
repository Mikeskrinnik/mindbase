from mindbase_shared.icloud import resolve_mindbase_root
from mindbase_shared.markdown import entry_to_markdown, obsidian_note_to_ingest, parse_frontmatter


def test_parse_frontmatter():
    content = '---\ntitle: "Test"\ntags: ["a", "b"]\n---\n\nBody here'
    meta, body = parse_frontmatter(content)
    assert meta["title"] == "Test"
    assert body == "Body here"


def test_obsidian_note_to_ingest():
    content = "---\ntitle: Meeting\n---\n\nDiscuss #project with team"
    payload = obsidian_note_to_ingest("notes/meeting.md", content)
    assert payload["source"] == "obsidian"
    assert payload["external_id"] == "obsidian:notes/meeting.md"
    assert "project" in payload["metadata"]["tags"]


def test_entry_to_markdown():
    md = entry_to_markdown(entry_id="abc-123", title="Hello", body="World", tags=["test"])
    assert "abc-123" in md
    assert "# Hello" in md
    assert "World" in md


def test_resolve_mindbase_root_fallback(tmp_path, monkeypatch):
    import mindbase_shared.icloud as icloud_mod

    monkeypatch.setattr(icloud_mod, "icloud_drive_root", lambda: None)
    root = resolve_mindbase_root(str(tmp_path / "Mindbase"))
    assert (root / "entries").is_dir()
    assert (root / "inbox").is_dir()
