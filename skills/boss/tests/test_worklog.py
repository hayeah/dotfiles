"""Tests for ``boss.worklog``."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from boss import worklog as wl
from boss import workspace


SAMPLE_FLAT = """\
---
status: working
section: Demo section
slug: demo
mode: worktree
spec: specs/main.md
created: 2026-04-11T07:30:16Z
---

> ## Demo section
>
> - [ ] implement per spec

## Todos
- [x] first thing
- [ ] second thing
  - context bullet

## Agent log
- 2026-04-11T14:00Z started

## Boss log

## Evidence

## Trouble report
"""

SAMPLE_PHASED = """\
---
status: working
section: Multi-phase
slug: multi
mode: worktree
spec: specs/main.md
created: 2026-04-11T07:30:16Z
---

## Todos

### phase one
- [x] did the thing
- [x] did another

### phase two
- [ ] still to do
- [ ] one more

## Agent log
- 2026-04-11T14:00Z kickoff

## Boss log

## Evidence

## Trouble report
"""


def test_parse_flat():
    w = wl.parse_worklog_text(SAMPLE_FLAT)
    assert w.frontmatter["slug"] == "demo"
    assert w.frontmatter["status"] == "working"
    assert "## Demo section" in w.section_quote
    assert len(w.phases) == 1
    phase = w.phases[0]
    assert phase.label is None
    assert [it.text for it in phase.items] == ["first thing", "second thing"]
    assert [it.checked for it in phase.items] == [True, False]
    assert w.progress == (1, 2)
    assert "started" in w.agent_log
    assert w.boss_log == ""


def test_parse_phased():
    w = wl.parse_worklog_text(SAMPLE_PHASED)
    assert len(w.phases) == 2
    assert w.phases[0].label == "phase one"
    assert w.phases[1].label == "phase two"
    assert w.progress == (2, 4)
    assert [it.text for it in w.phases[0].items] == ["did the thing", "did another"]


def test_parse_missing_frontmatter():
    text = "## Todos\n- [ ] no frontmatter\n"
    w = wl.parse_worklog_text(text)
    assert w.frontmatter == {}
    assert w.progress == (0, 1)


def test_append_boss_note_basic(tmp_path):
    path = tmp_path / "WORKLOG.md"
    path.write_text(SAMPLE_FLAT)
    ts = datetime(2026, 4, 11, 15, 42, tzinfo=timezone.utc)
    wl.append_boss_note(path, "don't use touch= with tree_digest", ts=ts)
    result = path.read_text()
    assert "- 2026-04-11T15:42Z don't use touch= with tree_digest" in result
    # Should land inside ## Boss log, before ## Evidence.
    boss_idx = result.index("## Boss log")
    ev_idx = result.index("## Evidence")
    note_idx = result.index("- 2026-04-11T15:42Z")
    assert boss_idx < note_idx < ev_idx


def test_append_boss_note_multiline(tmp_path):
    path = tmp_path / "WORKLOG.md"
    path.write_text(SAMPLE_FLAT)
    ts = datetime(2026, 4, 11, 15, 42, tzinfo=timezone.utc)
    wl.append_boss_note(path, "line one\nline two\nline three", ts=ts)
    result = path.read_text()
    assert "- 2026-04-11T15:42Z line one\n  line two\n  line three\n" in result


def test_append_agent_log(tmp_path):
    path = tmp_path / "WORKLOG.md"
    path.write_text(SAMPLE_FLAT)
    ts = datetime(2026, 4, 11, 15, 42, tzinfo=timezone.utc)
    wl.append_agent_log(path, "running pytest", ts=ts)
    w = wl.parse_worklog_text(path.read_text())
    assert "running pytest" in w.agent_log
    assert "2026-04-11T15:42Z" in w.agent_log


def test_append_creates_missing_section(tmp_path):
    """If ## Boss log is missing, it's inserted in canonical order."""
    text = (
        "---\nslug: x\n---\n\n"
        "## Todos\n- [ ] a\n\n"
        "## Agent log\n- 2026-04-11T14:00Z hi\n\n"
        "## Evidence\n\n"
        "## Trouble report\n"
    )
    path = tmp_path / "WORKLOG.md"
    path.write_text(text)
    ts = datetime(2026, 4, 11, 15, 42, tzinfo=timezone.utc)
    wl.append_boss_note(path, "new note", ts=ts)
    result = path.read_text()
    assert "## Boss log" in result
    boss_idx = result.index("## Boss log")
    ev_idx = result.index("## Evidence")
    assert boss_idx < ev_idx
    assert "- 2026-04-11T15:42Z new note" in result


def test_append_boss_note_twice_orders_correctly(tmp_path):
    path = tmp_path / "WORKLOG.md"
    path.write_text(SAMPLE_FLAT)
    t1 = datetime(2026, 4, 11, 15, 42, tzinfo=timezone.utc)
    t2 = datetime(2026, 4, 11, 16, 5, tzinfo=timezone.utc)
    wl.append_boss_note(path, "first", ts=t1)
    wl.append_boss_note(path, "second", ts=t2)
    result = path.read_text()
    i1 = result.index("first")
    i2 = result.index("second")
    assert i1 < i2
    # Both inside boss log.
    ev = result.index("## Evidence")
    assert i2 < ev


def test_set_section_quote_idempotent(tmp_path):
    path = tmp_path / "WORKLOG.md"
    path.write_text(SAMPLE_FLAT)
    body = "\n- [ ] new top-level item\n  - nested note\n"
    workspace.set_section_quote(path, body, "Demo section")
    first = path.read_text()
    workspace.set_section_quote(path, body, "Demo section")
    second = path.read_text()
    assert first == second
    assert "> ## Demo section" in first
    assert "> - [ ] new top-level item" in first
    # Only one blockquote marker group.
    assert first.count("> ## Demo section") == 1
    # Still parseable.
    w = wl.parse_worklog_text(first)
    assert w.frontmatter["slug"] == "demo"
    assert w.all_todos  # todos section intact


def test_set_section_quote_replaces_existing(tmp_path):
    path = tmp_path / "WORKLOG.md"
    path.write_text(SAMPLE_FLAT)
    workspace.set_section_quote(path, "\n- [ ] old\n", "Demo section")
    workspace.set_section_quote(path, "\n- [ ] new\n", "Demo section")
    text = path.read_text()
    assert "> - [ ] new" in text
    assert "> - [ ] old" not in text


def test_workspace_create_uses_new_template(tmp_path, monkeypatch):
    monkeypatch.setenv("BOSS_ROOT", str(tmp_path))
    lay = workspace.create("demo-slug", "Demo Header", "worktree")
    text = lay.worklog.read_text()
    # New section names.
    assert "## Agent log" in text
    assert "## Boss log" in text
    # Dropped sections.
    assert "## Status" not in text
    assert "## Log\n" not in text
    assert "## Notes from boss" not in text
    assert "## Questions for boss" not in text


def _find_real_worklogs() -> list[Path]:
    root = Path(os.environ.get("BOSS_ROOT", Path.home() / "Dropbox" / "boss"))
    if not root.is_dir():
        return []
    out: list[Path] = []
    for slug_dir in sorted(root.iterdir()):
        if not slug_dir.is_dir():
            continue
        if slug_dir.name.startswith("."):
            continue
        worklog = slug_dir / "WORKLOG.md"
        if worklog.is_file():
            out.append(worklog)
    return out


REAL_WORKLOGS = _find_real_worklogs()


@pytest.mark.skipif(not REAL_WORKLOGS, reason="no real $BOSS_ROOT worklogs available")
@pytest.mark.parametrize("path", REAL_WORKLOGS, ids=lambda p: p.parent.name)
def test_parse_real_worklog(path: Path):
    """Every real worklog in $BOSS_ROOT should parse without raising."""
    w = wl.parse_worklog_text(path.read_text())
    done, total = w.progress
    assert 0 <= done <= total
    # Frontmatter is present in the new template — older worklogs may use
    # the legacy template (## Status etc.) and that's fine, they just won't
    # have Boss log / Agent log fields populated. Don't assert shape, just
    # that parsing didn't crash.
