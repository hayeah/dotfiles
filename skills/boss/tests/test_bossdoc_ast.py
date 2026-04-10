"""Tests for the structured AST in bossdoc.py."""

from pathlib import Path

import pytest

from boss.bossdoc import (
    Checkbox,
    Prose,
    Section,
    find_nested_checkboxes,
    has_pending,
    is_spec_only,
    parse_body,
    parse_sections,
)

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# parse_body basics
# ---------------------------------------------------------------------------


def test_parse_body_empty():
    assert parse_body("", base_line=1) == []


def test_parse_body_blank_lines_only():
    assert parse_body("\n\n\n", base_line=1) == []


def test_parse_body_single_checkbox_unchecked():
    items = parse_body("- [ ] do the thing", base_line=5)
    assert len(items) == 1
    cb = items[0]
    assert isinstance(cb, Checkbox)
    assert cb.checked is False
    assert cb.text == "do the thing"
    assert cb.nested == []
    assert cb.line == 5


def test_parse_body_single_checkbox_checked():
    items = parse_body("- [x] done already", base_line=1)
    cb = items[0]
    assert cb.checked is True
    assert cb.text == "done already"


def test_parse_body_checkbox_uppercase_x():
    items = parse_body("- [X] DONE", base_line=1)
    assert items[0].checked is True


def test_parse_body_checkbox_with_nested():
    body = """\
- [ ] implement feature
  - step one
  - step two
  - [ ] nested checkbox"""
    items = parse_body(body, base_line=10)
    assert len(items) == 1
    cb = items[0]
    assert cb.text == "implement feature"
    assert cb.line == 10
    assert len(cb.nested) == 3
    assert cb.nested[0] == "  - step one"
    assert cb.nested[1] == "  - step two"
    assert cb.nested[2] == "  - [ ] nested checkbox"


def test_parse_body_prose():
    body = "Some explanatory text here.\nMore text on next line."
    items = parse_body(body, base_line=1)
    assert len(items) == 1
    p = items[0]
    assert isinstance(p, Prose)
    assert p.text == "Some explanatory text here.\nMore text on next line."
    assert p.line == 1


def test_parse_body_mixed():
    body = """\
Some preamble.

- [x] first done
- [ ] second pending
  - sub-item

Trailing prose."""
    items = parse_body(body, base_line=1)
    assert len(items) == 4
    assert isinstance(items[0], Prose)
    assert items[0].text == "Some preamble."
    assert items[0].line == 1

    assert isinstance(items[1], Checkbox)
    assert items[1].checked is True
    assert items[1].text == "first done"
    assert items[1].line == 3

    assert isinstance(items[2], Checkbox)
    assert items[2].checked is False
    assert items[2].text == "second pending"
    assert items[2].nested == ["  - sub-item"]
    assert items[2].line == 4

    assert isinstance(items[3], Prose)
    assert items[3].text == "Trailing prose."
    assert items[3].line == 7


def test_parse_body_consecutive_checkboxes():
    body = "- [ ] a\n- [x] b\n- [ ] c"
    items = parse_body(body, base_line=0)
    assert len(items) == 3
    assert [isinstance(i, Checkbox) for i in items] == [True, True, True]
    assert [i.text for i in items] == ["a", "b", "c"]
    assert [i.checked for i in items] == [False, True, False]


def test_parse_body_deeply_nested():
    body = """\
- [ ] top
  - level 1
    - level 2
      - level 3"""
    items = parse_body(body, base_line=1)
    assert len(items) == 1
    # Only the first level of indentation is captured as nested
    # Actually, any indented line following a checkbox is nested
    assert len(items[0].nested) == 3


def test_parse_body_tab_indented_nested():
    body = "- [ ] top\n\t- tab indented"
    items = parse_body(body, base_line=1)
    assert len(items) == 1
    assert items[0].nested == ["\t- tab indented"]


# ---------------------------------------------------------------------------
# parse_sections — line numbers and items
# ---------------------------------------------------------------------------


def test_parse_sections_header_line():
    text = """\
# Title

## First section

Some prose.

- [ ] a task

## Second section

- [x] done
"""
    sections = parse_sections(text)
    assert len(sections) == 2
    assert sections[0].header == "First section"
    assert sections[0].header_line == 3
    assert sections[1].header == "Second section"
    assert sections[1].header_line == 9


def test_parse_sections_items_populated():
    text = """\
# Title

## My section

Hello world.

- [ ] first task
  - detail
- [x] second task
"""
    sections = parse_sections(text)
    s = sections[0]
    assert len(s.items) == 3
    assert isinstance(s.items[0], Prose)
    assert s.items[0].text == "Hello world."
    assert isinstance(s.items[1], Checkbox)
    assert s.items[1].text == "first task"
    assert s.items[1].nested == ["  - detail"]
    assert isinstance(s.items[2], Checkbox)
    assert s.items[2].checked is True


def test_parse_sections_empty_body():
    text = "## Empty\n\n## Next\n\n- [ ] stuff"
    sections = parse_sections(text)
    assert len(sections) == 2
    assert sections[0].items == []
    assert len(sections[1].items) == 1


# ---------------------------------------------------------------------------
# Section methods
# ---------------------------------------------------------------------------


def test_section_has_pending_with_unchecked():
    s = Section(header="T", body="", slug="t", items=[
        Checkbox(checked=True, text="a", nested=[], line=1),
        Checkbox(checked=False, text="b", nested=[], line=2),
    ])
    assert s.has_pending() is True


def test_section_has_pending_all_checked():
    s = Section(header="T", body="", slug="t", items=[
        Checkbox(checked=True, text="a", nested=[], line=1),
        Checkbox(checked=True, text="b", nested=[], line=2),
    ])
    assert s.has_pending() is False


def test_section_has_pending_no_checkboxes():
    s = Section(header="T", body="", slug="t", items=[
        Prose(text="just text", line=1),
    ])
    assert s.has_pending() is False


def test_section_has_pending_empty_items():
    s = Section(header="T", body="", slug="t", items=[])
    assert s.has_pending() is False


def test_section_is_spec_only_true():
    s = Section(header="T", body="", slug="t", items=[
        Checkbox(checked=False, text="spec: write the design doc", nested=[], line=1),
        Checkbox(checked=True, text="done thing", nested=[], line=2),
    ])
    assert s.is_spec_only() is True


def test_section_is_spec_only_false():
    s = Section(header="T", body="", slug="t", items=[
        Checkbox(checked=False, text="implement feature", nested=[], line=1),
        Checkbox(checked=False, text="spec: write doc", nested=[], line=2),
    ])
    assert s.is_spec_only() is False


def test_section_is_spec_only_no_pending():
    s = Section(header="T", body="", slug="t", items=[
        Checkbox(checked=True, text="done", nested=[], line=1),
    ])
    assert s.is_spec_only() is False


def test_section_is_spec_only_case_insensitive():
    s = Section(header="T", body="", slug="t", items=[
        Checkbox(checked=False, text="Spec: Write design", nested=[], line=1),
    ])
    assert s.is_spec_only() is True


def test_section_find_nested_checkboxes():
    s = Section(header="T", body="", slug="t", items=[
        Checkbox(checked=False, text="top", nested=[
            "  - plain bullet",
            "  - [ ] nested checkbox",
            "  - [x] nested done",
        ], line=1),
        Checkbox(checked=True, text="done", nested=[], line=5),
    ])
    nested = s.find_nested_checkboxes()
    assert len(nested) == 2
    assert "  - [ ] nested checkbox" in nested
    assert "  - [x] nested done" in nested


def test_section_find_nested_checkboxes_none():
    s = Section(header="T", body="", slug="t", items=[
        Checkbox(checked=False, text="top", nested=["  - plain"], line=1),
    ])
    assert s.find_nested_checkboxes() == []


# ---------------------------------------------------------------------------
# Standalone function wrappers (backward compat)
# ---------------------------------------------------------------------------


def test_has_pending_standalone():
    body = "- [ ] pending\n- [x] done"
    assert has_pending(body) is True


def test_has_pending_standalone_all_done():
    body = "- [x] done\n- [x] also done"
    assert has_pending(body) is False


def test_has_pending_standalone_no_checkboxes():
    body = "Just some prose."
    assert has_pending(body) is False


def test_is_spec_only_standalone():
    body = "- [ ] spec: design doc\n- [x] old task"
    assert is_spec_only(body) is True


def test_is_spec_only_standalone_false():
    body = "- [ ] implement thing"
    assert is_spec_only(body) is False


def test_find_nested_checkboxes_standalone():
    body = "- [ ] top\n  - [ ] nested\n  - plain"
    result = find_nested_checkboxes(body)
    assert len(result) == 1
    assert "  - [ ] nested" in result[0]


def test_find_nested_checkboxes_standalone_none():
    body = "- [ ] top\n  - plain bullet"
    assert find_nested_checkboxes(body) == []


# ---------------------------------------------------------------------------
# Real BOSS.md fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def boss_md():
    return (FIXTURES / "BOSS.md").read_text()


def test_real_boss_md_parses(boss_md):
    """BOSS.md parses without errors and produces sections with items."""
    sections = parse_sections(boss_md)
    assert len(sections) > 0
    # Every section should have a slug
    for s in sections:
        assert s.slug
        assert s.header_line > 0


def test_real_boss_md_has_checkboxes(boss_md):
    """Real BOSS.md should have sections with checkboxes."""
    sections = parse_sections(boss_md)
    sections_with_cbs = [
        s for s in sections
        if any(isinstance(i, Checkbox) for i in s.items)
    ]
    assert len(sections_with_cbs) > 0


def test_real_boss_md_has_prose(boss_md):
    """Real BOSS.md should have sections with prose."""
    sections = parse_sections(boss_md)
    sections_with_prose = [
        s for s in sections
        if any(isinstance(i, Prose) for i in s.items)
    ]
    assert len(sections_with_prose) > 0


def test_real_boss_md_has_nested_bullets(boss_md):
    """Real BOSS.md should have checkboxes with nested bullets."""
    sections = parse_sections(boss_md)
    found = False
    for s in sections:
        for item in s.items:
            if isinstance(item, Checkbox) and item.nested:
                found = True
                break
        if found:
            break
    assert found


def test_real_boss_md_line_numbers_monotonic(boss_md):
    """Line numbers within each section should be monotonically increasing."""
    sections = parse_sections(boss_md)
    for s in sections:
        prev = 0
        for item in s.items:
            assert item.line > prev or prev == 0
            prev = item.line


def test_real_boss_md_has_pending_matches_standalone(boss_md):
    """Section.has_pending() should agree with has_pending(body) for all sections."""
    sections = parse_sections(boss_md)
    for s in sections:
        assert s.has_pending() == has_pending(s.body), f"mismatch on {s.slug}"


def test_real_boss_md_is_spec_only_matches_standalone(boss_md):
    """Section.is_spec_only() should agree with is_spec_only(body) for all sections."""
    sections = parse_sections(boss_md)
    for s in sections:
        assert s.is_spec_only() == is_spec_only(s.body), f"mismatch on {s.slug}"


def test_real_boss_md_find_nested_matches_standalone(boss_md):
    """Section.find_nested_checkboxes() should agree with standalone version."""
    sections = parse_sections(boss_md)
    for s in sections:
        assert s.find_nested_checkboxes() == find_nested_checkboxes(s.body), \
            f"mismatch on {s.slug}"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_checkbox_text_with_special_chars():
    body = "- [ ] fix `bug #123` in foo/bar.py (urgent!)"
    items = parse_body(body, base_line=1)
    assert items[0].text == "fix `bug #123` in foo/bar.py (urgent!)"


def test_checkbox_text_with_colon():
    body = "- [ ] spec: some design doc"
    items = parse_body(body, base_line=1)
    assert items[0].text == "spec: some design doc"


def test_prose_with_code_block():
    body = """\
Some context:

```python
x = 1
```

- [ ] task after code"""
    items = parse_body(body, base_line=1)
    # Prose should capture the code block too
    assert isinstance(items[0], Prose)
    assert "```python" in items[0].text
    assert isinstance(items[-1], Checkbox)
    assert items[-1].text == "task after code"


def test_section_with_only_prose():
    text = "## Prose only\n\nJust some text.\nMore text."
    sections = parse_sections(text)
    s = sections[0]
    assert len(s.items) == 1
    assert isinstance(s.items[0], Prose)
    assert s.has_pending() is False
    assert s.is_spec_only() is False


def test_multiple_spec_checkboxes():
    s = Section(header="T", body="", slug="t", items=[
        Checkbox(checked=False, text="spec: doc A", nested=[], line=1),
        Checkbox(checked=False, text="spec: doc B", nested=[], line=2),
    ])
    assert s.is_spec_only() is True


def test_line_numbers_across_sections():
    text = """\
# Title

## First

- [ ] task one

## Second

- [x] task two
"""
    sections = parse_sections(text)
    # First section header at line 3, task at line 5
    assert sections[0].header_line == 3
    assert sections[0].items[0].line == 5
    # Second section header at line 7, task at line 9
    assert sections[1].header_line == 7
    assert sections[1].items[0].line == 9
