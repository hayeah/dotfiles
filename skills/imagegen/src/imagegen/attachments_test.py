"""Tests for attachments module."""

from __future__ import annotations

import base64
from pathlib import Path

from .attachments import Attachment, load_attachment


def test_load_image_attachment(tmp_path: Path) -> None:
    img = tmp_path / "photo.png"
    raw = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    img.write_bytes(raw)

    att = load_attachment(img)

    assert att.is_image is True
    assert att.data == base64.b64encode(raw).decode("ascii")
    assert att.mime_type == "image/png"
    assert att.data_url.startswith("data:image/png;base64,")


def test_load_text_attachment(tmp_path: Path) -> None:
    txt = tmp_path / "notes.txt"
    txt.write_text("Draw a cat.\nMake it fluffy.", encoding="utf-8")

    att = load_attachment(txt)

    assert att.is_image is False
    assert att.data == "Draw a cat.\nMake it fluffy."


def test_image_extensions(tmp_path: Path) -> None:
    for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".svg"]:
        f = tmp_path / f"img{ext}"
        f.write_bytes(b"\x00")
        att = load_attachment(f)
        assert att.is_image is True, f"Expected {ext} to be classified as image"


def test_non_image_extensions(tmp_path: Path) -> None:
    for ext in [".txt", ".md", ".py", ".json", ".csv"]:
        f = tmp_path / f"file{ext}"
        f.write_text("content", encoding="utf-8")
        att = load_attachment(f)
        assert att.is_image is False, f"Expected {ext} to be classified as text"


def test_data_url_format() -> None:
    att = Attachment(path=Path("test.jpg"), is_image=True, data="AAAA")
    assert att.data_url == "data:image/jpeg;base64,AAAA"
