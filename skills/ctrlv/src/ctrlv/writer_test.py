"""Tests for ClipboardWriter."""

from __future__ import annotations

from pathlib import Path

import pytest

from .clipboard import FileItem, ImageItem, TextItem
from .writer import ClipboardWriter


@pytest.fixture
def dest(tmp_path: Path) -> Path:
    d = tmp_path / "output"
    d.mkdir()
    return d


class TestWriteText:
    def test_writes_indexed_txt(self, dest: Path) -> None:
        writer = ClipboardWriter(dest)
        result = writer.write_all([TextItem(text="hello world")])
        assert result.items[0].path == dest / "1.txt"
        assert (dest / "1.txt").read_text() == "hello world"

    def test_multiple_text_items_numbered(self, dest: Path) -> None:
        writer = ClipboardWriter(dest)
        result = writer.write_all([TextItem(text="first"), TextItem(text="second")])
        assert result.items[0].path == dest / "1.txt"
        assert result.items[1].path == dest / "2.txt"
        assert (dest / "2.txt").read_text() == "second"


class TestWriteImage:
    def test_writes_indexed_png(self, dest: Path) -> None:
        data = b"\x89PNG fake"
        writer = ClipboardWriter(dest)
        result = writer.write_all([ImageItem(data=data, ext="png")])
        assert result.items[0].path == dest / "1.png"
        assert (dest / "1.png").read_bytes() == data

    def test_multiple_images_numbered(self, dest: Path) -> None:
        writer = ClipboardWriter(dest)
        result = writer.write_all([
            ImageItem(data=b"a", ext="png"),
            ImageItem(data=b"b", ext="png"),
        ])
        assert result.items[0].path == dest / "1.png"
        assert result.items[1].path == dest / "2.png"


class TestWriteFiles:
    def test_preserves_original_filename(self, dest: Path, tmp_path: Path) -> None:
        src = tmp_path / "src" / "report.pdf"
        src.parent.mkdir()
        src.write_bytes(b"pdf content")

        writer = ClipboardWriter(dest)
        result = writer.write_all([FileItem(path=src)])
        assert result.items[0].path == dest / "report.pdf"
        assert (dest / "report.pdf").read_bytes() == b"pdf content"

    def test_collision_adds_suffix(self, dest: Path, tmp_path: Path) -> None:
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        a = src_dir / "a" / "photo.jpg"
        b = src_dir / "b" / "photo.jpg"
        a.parent.mkdir()
        b.parent.mkdir()
        a.write_bytes(b"img1")
        b.write_bytes(b"img2")

        writer = ClipboardWriter(dest)
        result = writer.write_all([FileItem(path=a), FileItem(path=b)])
        assert result.items[0].path == dest / "photo.jpg"
        assert result.items[1].path == dest / "photo_2.jpg"
        assert (dest / "photo_2.jpg").read_bytes() == b"img2"

    def test_file_without_extension(self, dest: Path, tmp_path: Path) -> None:
        src = tmp_path / "src" / "Makefile"
        src.parent.mkdir()
        src.write_bytes(b"make content")

        writer = ClipboardWriter(dest)
        result = writer.write_all([FileItem(path=src)])
        assert result.items[0].path == dest / "Makefile"

    def test_collision_no_extension(self, dest: Path, tmp_path: Path) -> None:
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        a = src_dir / "a" / "Makefile"
        b = src_dir / "b" / "Makefile"
        a.parent.mkdir()
        b.parent.mkdir()
        a.write_bytes(b"a")
        b.write_bytes(b"b")

        writer = ClipboardWriter(dest)
        result = writer.write_all([FileItem(path=a), FileItem(path=b)])
        assert result.items[0].path == dest / "Makefile"
        assert result.items[1].path == dest / "Makefile_2"


class TestWipe:
    def test_wipes_dir_on_each_run(self, dest: Path) -> None:
        writer = ClipboardWriter(dest)
        writer.write_all([TextItem(text="first"), ImageItem(data=b"img", ext="png")])
        assert (dest / "1.txt").exists()
        assert (dest / "2.png").exists()

        writer.write_all([TextItem(text="second")])
        assert (dest / "1.txt").read_text() == "second"
        assert not (dest / "2.png").exists()
