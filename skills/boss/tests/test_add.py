"""Tests for `boss add` — appending sections with date grouping."""

from pathlib import Path

from typer.testing import CliRunner

from boss import bossdoc, main

runner = CliRunner()


# --- bossdoc.append_section unit tests ---


def test_append_to_nonexistent_file(tmp_path):
    doc = tmp_path / "BOSS.md"
    slug = bossdoc.append_section(doc, "## New feature\n\n- [ ] do it\n", "2026-04-10")
    assert slug == "new-feature"
    text = doc.read_text()
    assert text.startswith("# 2026-04-10\n")
    assert "## New feature" in text
    assert "- [ ] do it" in text


def test_append_to_existing_date_group(tmp_path):
    doc = tmp_path / "BOSS.md"
    doc.write_text("# 2026-04-10\n\n## First thing\n\n- [ ] alpha\n")

    slug = bossdoc.append_section(doc, "## Second thing\n\n- [ ] beta\n", "2026-04-10")
    assert slug == "second-thing"
    text = doc.read_text()
    # Both sections under same date header.
    assert text.count("# 2026-04-10") == 1
    assert "## First thing" in text
    assert "## Second thing" in text
    # Second should come after first.
    assert text.index("## First thing") < text.index("## Second thing")


def test_append_creates_new_date_group(tmp_path):
    doc = tmp_path / "BOSS.md"
    doc.write_text("# 2026-04-09\n\n## Old task\n\n- [x] done\n")

    slug = bossdoc.append_section(doc, "## New task\n\n- [ ] todo\n", "2026-04-10")
    assert slug == "new-task"
    text = doc.read_text()
    assert "# 2026-04-09" in text
    assert "# 2026-04-10" in text
    assert "## New task" in text


def test_append_between_date_groups(tmp_path):
    """Appending to an earlier date group inserts before the next date group."""
    doc = tmp_path / "BOSS.md"
    doc.write_text(
        "# 2026-04-09\n\n## Task A\n\n- [ ] a\n\n"
        "# 2026-04-10\n\n## Task C\n\n- [ ] c\n"
    )

    bossdoc.append_section(doc, "## Task B\n\n- [ ] b\n", "2026-04-09")
    text = doc.read_text()
    # Task B should be under 2026-04-09, before the 2026-04-10 group.
    assert text.index("## Task A") < text.index("## Task B") < text.index("# 2026-04-10")


def test_append_rejects_duplicate_slug(tmp_path):
    doc = tmp_path / "BOSS.md"
    doc.write_text("# 2026-04-10\n\n## My feature\n\n- [ ] x\n")

    import pytest
    with pytest.raises(bossdoc.BossDocError, match="already exists"):
        bossdoc.append_section(doc, "## My feature\n\n- [ ] y\n", "2026-04-10")


def test_append_rejects_empty_text(tmp_path):
    doc = tmp_path / "BOSS.md"
    import pytest
    with pytest.raises(bossdoc.BossDocError, match="empty"):
        bossdoc.append_section(doc, "   \n", "2026-04-10")


def test_append_rejects_no_header(tmp_path):
    doc = tmp_path / "BOSS.md"
    import pytest
    with pytest.raises(bossdoc.BossDocError, match="## header"):
        bossdoc.append_section(doc, "just some text\n- [ ] no header\n", "2026-04-10")


# --- CLI integration tests ---


def test_add_cli_reads_stdin(tmp_path):
    doc = tmp_path / "BOSS.md"
    result = runner.invoke(
        main.app,
        ["add", "--boss-doc", str(doc), "--date", "2026-04-10"],
        input="## CLI feature\n\n- [ ] implement\n",
    )
    assert result.exit_code == 0, result.output
    assert "added: cli-feature" in result.output
    assert "date group: 2026-04-10" in result.output
    assert doc.exists()
    assert "## CLI feature" in doc.read_text()


def test_add_cli_empty_stdin(tmp_path):
    doc = tmp_path / "BOSS.md"
    result = runner.invoke(
        main.app,
        ["add", "--boss-doc", str(doc)],
        input="",
    )
    assert result.exit_code == 2
    assert "no section text" in result.output


def test_add_cli_duplicate_slug(tmp_path):
    doc = tmp_path / "BOSS.md"
    doc.write_text("# 2026-04-10\n\n## Existing\n\n- [ ] x\n")
    result = runner.invoke(
        main.app,
        ["add", "--boss-doc", str(doc), "--date", "2026-04-10"],
        input="## Existing\n\n- [ ] y\n",
    )
    assert result.exit_code == 1
    assert "already exists" in result.output
