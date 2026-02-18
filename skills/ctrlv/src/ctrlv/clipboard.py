"""Read items from the macOS (iCloud) clipboard via NSPasteboard."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Union

import AppKit

log = logging.getLogger(__name__)

# UTI type constants
TYPE_STRING = "public.utf8-plain-text"
TYPE_PNG = "public.png"
TYPE_JPEG = "public.jpeg"
TYPE_TIFF = "public.tiff"
TYPE_FILE_URL = "public.file-url"

# Ordered by preference when reading images
IMAGE_TYPES = [
    (TYPE_PNG, "png"),
    (TYPE_JPEG, "jpg"),
    (TYPE_TIFF, "tiff"),
]


@dataclass
class TextItem:
    text: str


@dataclass
class ImageItem:
    data: bytes
    ext: str


@dataclass
class FileItem:
    path: Path


ClipboardItem = Union[TextItem, ImageItem, FileItem]


class ClipboardReader:
    def __init__(self) -> None:
        self.pasteboard = AppKit.NSPasteboard.generalPasteboard()

    def items(self) -> list[ClipboardItem]:
        """Return all items from the current clipboard, highest-priority type first."""
        pb_items = self.pasteboard.pasteboardItems() or []
        result: list[ClipboardItem] = []
        text_added = False

        for pb_item in pb_items:
            item = self._read_item(pb_item, include_text=not text_added)
            if item is not None:
                result.append(item)
                if isinstance(item, TextItem):
                    text_added = True

        return result

    def _read_item(self, pb_item: Any, include_text: bool = True) -> ClipboardItem | None:
        # Priority: file URL > image > text
        file_item = self._try_file_url(pb_item)
        if file_item is not None:
            return file_item

        image_item = self._try_image(pb_item)
        if image_item is not None:
            return image_item

        if include_text:
            return self._try_text(pb_item)

        return None

    def _try_file_url(self, pb_item: Any) -> FileItem | None:
        url_str = pb_item.stringForType_(TYPE_FILE_URL)
        if not url_str:
            return None
        url = AppKit.NSURL.URLWithString_(url_str)
        if url and url.isFileURL():
            return FileItem(path=Path(url.path()))
        return None

    def _try_image(self, pb_item: Any) -> ImageItem | None:
        for type_id, ext in IMAGE_TYPES:
            data = pb_item.dataForType_(type_id)
            if data:
                return ImageItem(data=bytes(data), ext=ext)
        return None

    def _try_text(self, pb_item: Any) -> TextItem | None:
        text = pb_item.stringForType_(TYPE_STRING)
        if text:
            return TextItem(text=str(text))
        return None
