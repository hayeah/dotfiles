"""Write clipboard items to files in the destination directory."""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .clipboard import ClipboardItem, FileItem, ImageItem, TextItem

log = logging.getLogger(__name__)


@dataclass
class WrittenItem:
    index: int
    path: Path
    item: ClipboardItem


@dataclass
class WriteResult:
    items: list[WrittenItem] = field(default_factory=list)

    @property
    def text(self) -> str | None:
        for wi in self.items:
            if isinstance(wi.item, TextItem):
                return wi.item.text
        return None


class ClipboardWriter:
    def __init__(self, dest_dir: Path) -> None:
        self.dest_dir = dest_dir

    def write_all(self, items: list[ClipboardItem], append: bool = False) -> WriteResult:
        """Write all items to dest_dir. Wipes first unless append=True."""
        if append:
            self.dest_dir.mkdir(parents=True, exist_ok=True)
        else:
            self._reset()
        result = WriteResult()
        for i, item in enumerate(items, start=1):
            path = self._write_item(i, item)
            result.items.append(WrittenItem(index=i, path=path, item=item))
        return result

    def _reset(self) -> None:
        if self.dest_dir.exists():
            shutil.rmtree(self.dest_dir)
        self.dest_dir.mkdir(parents=True)

    def _unique_path(self, name: str) -> Path:
        """Return a path in dest_dir that doesn't collide, adding _{i} if needed."""
        path = self.dest_dir / name
        if not path.exists():
            return path
        stem = Path(name).stem
        suffix = Path(name).suffix
        i = 2
        while True:
            path = self.dest_dir / f"{stem}_{i}{suffix}"
            if not path.exists():
                return path
            i += 1

    def _write_item(self, index: int, item: ClipboardItem) -> Path:
        if isinstance(item, TextItem):
            path = self.dest_dir / f"{index}.txt"
            path.write_text(item.text, encoding="utf-8")
        elif isinstance(item, ImageItem):
            path = self.dest_dir / f"{index}.{item.ext}"
            path.write_bytes(item.data)
        elif isinstance(item, FileItem):
            path = self._unique_path(item.path.name)
            shutil.copy2(item.path, path)
        else:
            raise TypeError(f"Unknown item type: {type(item)}")
        log.debug("Wrote item %d to %s", index, path)
        return path
