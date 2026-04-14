"""Tests for `boss close` — tombstone insertion and idempotency."""

from pathlib import Path

import pytest

from boss import bossdoc, close, workspace


def test_is_closed_roundtrip():
    assert bossdoc.is_closed("- [ ] todo\n") is False
    assert bossdoc.is_closed("<!-- closed: 2026-04-14 -->\n- [ ] todo\n") is True
    # Extra internal whitespace is tolerated.
    assert bossdoc.is_closed("<!--  closed:  2026-04-14  -->\n") is True
    # Wrong format — reject.
    assert bossdoc.is_closed("<!-- closed: today -->\n") is False
    assert bossdoc.is_closed("<!-- closed 2026-04-14 -->\n") is False


def test_section_is_closed_property():
    text = (
        "# 2026-04-14\n\n"
        "## Feature A\n\n"
        "<!-- closed: 2026-04-14 -->\n\n"
        "- [ ] still open\n\n"
        "## Feature B\n\n"
        "- [ ] not yet\n"
    )
    secs = bossdoc.parse_sections(text)
    assert secs[0].is_closed() is True
    assert secs[1].is_closed() is False


def test_close_section_inserts_marker(tmp_path, monkeypatch):
    monkeypatch.setenv("BOSS_ROOT", str(tmp_path / "boss"))
    doc = tmp_path / "BOSS.md"
    doc.write_text(
        "# 2026-04-14\n\n"
        "## Feature A\n\n"
        "- [ ] still open\n"
        "- [ ] also open\n\n"
        "## Feature B\n\n"
        "- [ ] later\n"
    )

    result = close.close_section(doc, "feature-a", today="2026-04-14")
    assert result.already_closed is False
    assert result.slug == "feature-a"
    assert result.killed_agent is None

    text = doc.read_text()
    assert "<!-- closed: 2026-04-14 -->" in text
    # Marker is in the Feature A section, before the checkboxes.
    feature_a_pos = text.index("## Feature A")
    marker_pos = text.index("<!-- closed: 2026-04-14 -->")
    cb_pos = text.index("- [ ] still open")
    feature_b_pos = text.index("## Feature B")
    assert feature_a_pos < marker_pos < cb_pos < feature_b_pos
    # Feature B untouched.
    assert text.count("<!-- closed:") == 1


def test_close_section_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("BOSS_ROOT", str(tmp_path / "boss"))
    doc = tmp_path / "BOSS.md"
    doc.write_text(
        "## Feature A\n\n"
        "<!-- closed: 2026-04-10 -->\n\n"
        "- [ ] still open\n"
    )
    result = close.close_section(doc, "feature-a", today="2026-04-14")
    assert result.already_closed is True
    # Doc unchanged.
    assert doc.read_text().count("<!-- closed:") == 1
    assert "2026-04-10" in doc.read_text()


def test_close_section_unknown(tmp_path, monkeypatch):
    monkeypatch.setenv("BOSS_ROOT", str(tmp_path / "boss"))
    doc = tmp_path / "BOSS.md"
    doc.write_text("## Feature A\n\n- [ ] x\n")
    with pytest.raises(close.CloseError):
        close.close_section(doc, "nonexistent")


def test_close_section_kills_live_agent(tmp_path, monkeypatch):
    """`boss close` kills the live agent session recorded in .boss.json."""
    monkeypatch.setenv("BOSS_ROOT", str(tmp_path / "boss"))
    doc = tmp_path / "BOSS.md"
    doc.write_text("## Feature A\n\n- [ ] open\n")

    lay = workspace.create("feature-a", "Feature A", "worktree")
    workspace.update_boss_json(lay.root, updates={"agent_id": "abc123"})

    killed = []

    from boss import agentboss

    def fake_kill(key: str) -> None:
        killed.append(key)

    monkeypatch.setattr(agentboss, "kill", fake_kill)

    result = close.close_section(doc, "feature-a", today="2026-04-14")
    assert result.killed_agent == "abc123"
    assert killed == ["abc123"]


def test_close_section_tolerates_dead_agent(tmp_path, monkeypatch):
    monkeypatch.setenv("BOSS_ROOT", str(tmp_path / "boss"))
    doc = tmp_path / "BOSS.md"
    doc.write_text("## Feature A\n\n- [ ] open\n")

    lay = workspace.create("feature-a", "Feature A", "worktree")
    workspace.update_boss_json(lay.root, updates={"agent_id": "abc123"})

    from boss import agentboss

    def fake_kill(key: str) -> None:
        raise agentboss.AgentbossError("no such session")

    monkeypatch.setattr(agentboss, "kill", fake_kill)
    # Should not raise.
    result = close.close_section(doc, "feature-a", today="2026-04-14")
    assert result.killed_agent is None
    assert result.already_closed is False


def test_close_section_preserves_other_sections(tmp_path, monkeypatch):
    monkeypatch.setenv("BOSS_ROOT", str(tmp_path / "boss"))
    doc = tmp_path / "BOSS.md"
    orig = (
        "# 2026-04-14\n\n"
        "## Keep Me\n\n"
        "- [ ] untouched\n\n"
        "## Close Me\n\n"
        "- [ ] will be closed\n\n"
        "## Also Keep\n\n"
        "- [x] done\n"
    )
    doc.write_text(orig)
    close.close_section(doc, "close-me", today="2026-04-14")
    new = doc.read_text()

    # "Keep Me" body unchanged.
    keep_body = new[new.index("## Keep Me") : new.index("## Close Me")]
    assert "closed:" not in keep_body
    assert "- [ ] untouched" in keep_body

    # "Also Keep" body unchanged.
    after = new[new.index("## Also Keep") :]
    assert "closed:" not in after
    assert "- [x] done" in after
