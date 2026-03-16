"""Image generation with OpenAI and Gemini providers.

OpenAI usage:

    from hayeah.imagegen.openai import OpenAIProvider

    p = OpenAIProvider()

    # Responses API (streaming, multi-turn, attachments)
    results = p.generate("a cat wearing a top hat")
    results[0].save("cat.png")

    # With options
    results = p.generate("a logo", size="1024x1024", quality="high", background="transparent")

    # Multi-turn editing
    r1 = p.generate("a cat in a garden")
    r2 = p.generate("make it orange", previous_response_id=r1[0].metadata["response_id"])

    # Streaming partial previews
    def on_preview(index, data):
        Path(f"preview-{index}.png").write_bytes(data)

    results = p.generate("a river", on_partial=on_preview)

    # Images API (direct, no text model — faster for simple prompts)
    p_direct = OpenAIProvider(model=None)
    results = p_direct.generate("a simple icon", n=3)

    # Edit an existing image
    p_direct.edit("make the hat blue", images=[Path("cat.png").read_bytes()])[0].save("cat-blue.png")

Gemini usage:

    from hayeah.imagegen.gemini import GeminiProvider

    p = GeminiProvider()

    # Gemini native model
    results = p.generate("a landscape", aspect_ratio="16:9", image_size="2K")
    results[0].save("landscape.png")

    # Imagen model
    p_imagen = GeminiProvider(model="imagen-4.0-generate-001")
    results = p_imagen.generate("a photo", n=2)

    # With reference image
    results = p.generate("remix this", images=[Path("ref.png").read_bytes()])

Both providers return list[ImageResult].
"""

from __future__ import annotations

__all__ = ["ImageResult", "output_format_from_path"]

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
