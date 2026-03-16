"""Image generation with OpenAI and Gemini providers.

Each provider has its own module with its own API:

    from hayeah.imagegen.openai import OpenAIProvider
    p = OpenAIProvider()
    p.generate("a cat")[0].save("cat.png")

    from hayeah.imagegen.gemini import GeminiProvider
    p = GeminiProvider()
    p.generate("a landscape", aspect_ratio="16:9")[0].save("landscape.png")

Both return list[ImageResult].
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ImageResult:
    """A single generated image.

    Attributes:
        data: Raw image bytes (PNG, JPEG, or WebP).
        format: Image format — "png", "jpeg", or "webp".
        metadata: Provider-specific info.
            OpenAI: {"response_id": str, "model": str, ...}
            Gemini: {"model": str}
    """

    data: bytes
    format: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def save(self, path: Path | str) -> Path:
        """Write image to disk. Creates parent dirs. Returns the path."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(self.data)
        return p


def output_format_from_path(path: Path | str | None) -> str:
    """Infer output format from a file path extension."""
    if path is None:
        return "png"
    ext = Path(path).suffix.lower()
    return {".png": "png", ".webp": "webp", ".jpg": "jpeg", ".jpeg": "jpeg"}.get(ext, "png")
