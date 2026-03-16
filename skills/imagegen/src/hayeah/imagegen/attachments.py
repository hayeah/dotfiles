"""Attachment loading — classify image vs text, read/encode."""

from __future__ import annotations

import base64
import mimetypes
from dataclasses import dataclass
from pathlib import Path

IMAGE_EXTENSIONS = frozenset(
    {
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".webp",
        ".bmp",
        ".tiff",
        ".svg",
    }
)


@dataclass
class Attachment:
    path: Path
    is_image: bool
    # For images: base64-encoded data. For text: file contents.
    data: str

    @property
    def mime_type(self) -> str:
        mime, _ = mimetypes.guess_type(str(self.path))
        return mime or "application/octet-stream"

    @property
    def data_url(self) -> str:
        return f"data:{self.mime_type};base64,{self.data}"


def load_attachment(path: Path) -> Attachment:
    """Load a file as an Attachment, classifying it as image or text."""
    suffix = path.suffix.lower()
    is_image = suffix in IMAGE_EXTENSIONS

    if is_image:
        raw = path.read_bytes()
        data = base64.b64encode(raw).decode("ascii")
    else:
        data = path.read_text(encoding="utf-8")

    return Attachment(path=path, is_image=is_image, data=data)
