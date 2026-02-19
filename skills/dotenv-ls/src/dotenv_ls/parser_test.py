"""Tests for dotenv parser."""

from __future__ import annotations

from pathlib import Path

from .parser import parse_env_file, parse_env_files


class TestParseEnvFile:
    def test_basic(self, tmp_path: Path) -> None:
        f = tmp_path / ".env"
        f.write_text("FOO=bar\nBAZ=qux\n")
        entries = parse_env_file(f)
        assert [e.name for e in entries] == ["FOO", "BAZ"]
        assert all(e.comment is None for e in entries)

    def test_skips_blanks(self, tmp_path: Path) -> None:
        f = tmp_path / ".env"
        f.write_text("\nFOO=bar\n\nBAR=baz\n")
        assert [e.name for e in parse_env_file(f)] == ["FOO", "BAR"]

    def test_export_prefix(self, tmp_path: Path) -> None:
        f = tmp_path / ".env"
        f.write_text("export FOO=bar\nexport BAZ=qux\n")
        assert [e.name for e in parse_env_file(f)] == ["FOO", "BAZ"]

    def test_quoted_values(self, tmp_path: Path) -> None:
        f = tmp_path / ".env"
        f.write_text("FOO='bar'\nBAZ=\"qux\"\n")
        assert [e.name for e in parse_env_file(f)] == ["FOO", "BAZ"]

    def test_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path / ".env"
        f.write_text("")
        assert parse_env_file(f) == []

    def test_preceding_comment(self, tmp_path: Path) -> None:
        f = tmp_path / ".env"
        f.write_text("# API key for OpenAI\nOPENAI_KEY=sk-123\nNO_COMMENT=val\n")
        entries = parse_env_file(f)
        assert entries[0].name == "OPENAI_KEY"
        assert entries[0].comment == "# API key for OpenAI"
        assert entries[1].name == "NO_COMMENT"
        assert entries[1].comment is None

    def test_blank_line_clears_comment(self, tmp_path: Path) -> None:
        f = tmp_path / ".env"
        f.write_text("# orphan comment\n\nFOO=bar\n")
        entries = parse_env_file(f)
        assert entries[0].name == "FOO"
        assert entries[0].comment is None

    def test_only_last_comment_kept(self, tmp_path: Path) -> None:
        f = tmp_path / ".env"
        f.write_text("# first comment\n# second comment\nFOO=bar\n")
        entries = parse_env_file(f)
        assert entries[0].comment == "# second comment"


class TestParseEnvFiles:
    def test_later_file_overrides(self, tmp_path: Path) -> None:
        f1 = tmp_path / "base.env"
        f1.write_text("FOO=1\nBAR=2\n")
        f2 = tmp_path / "local.env"
        f2.write_text("FOO=override\nBAZ=3\n")
        entries = parse_env_files([f1, f2])
        resolved = {e.name: e.filepath for e in entries}
        assert resolved["FOO"] == str(f2)
        assert resolved["BAR"] == str(f1)
        assert resolved["BAZ"] == str(f2)

    def test_single_file(self, tmp_path: Path) -> None:
        f = tmp_path / ".env"
        f.write_text("A=1\nB=2\n")
        entries = parse_env_files([f])
        assert len(entries) == 2

    def test_override_preserves_comment_from_winner(self, tmp_path: Path) -> None:
        f1 = tmp_path / "base.env"
        f1.write_text("# base comment\nFOO=1\n")
        f2 = tmp_path / "local.env"
        f2.write_text("# local comment\nFOO=2\n")
        entries = parse_env_files([f1, f2])
        assert entries[0].name == "FOO"
        assert entries[0].comment == "# local comment"
