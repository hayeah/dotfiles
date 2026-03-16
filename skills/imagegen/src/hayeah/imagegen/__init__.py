"""Image generation with OpenAI and Gemini providers.

Providers:
    OpenAI — GPT-5 Responses API (streaming, multi-turn) or direct Images API.
    Gemini — native Gemini image models or Imagen models.

Quick start:
    from hayeah.imagegen import generate
    results = generate("a cat wearing a top hat")
    results[0].save("cat.png")
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


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


def _resolve_images(images: list[bytes | Path] | None) -> list[bytes]:
    """Convert a mix of bytes and Paths to a list of bytes."""
    if not images:
        return []
    return [p.read_bytes() if isinstance(p, Path) else p for p in images]


def _output_format_from_path(path: Path | str | None) -> str:
    """Infer output format from a file path extension."""
    if path is None:
        return "png"
    ext = Path(path).suffix.lower()
    return {".png": "png", ".webp": "webp", ".jpg": "jpeg", ".jpeg": "jpeg"}.get(ext, "png")


def generate(
    prompt: str,
    *,
    provider: Literal["openai", "gemini"] = "openai",
    model: str | None = None,
    images: list[bytes | Path] | None = None,
    n: int = 1,
    size: str = "auto",
    quality: str = "auto",
    output_format: str = "png",
    # OpenAI-specific
    background: str = "auto",
    previous_response_id: str | None = None,
    on_partial: Callable[[int, bytes], None] | None = None,
    partial_images: int = 3,
    # Gemini-specific
    aspect_ratio: str = "1:1",
    image_size: str = "1K",
) -> list[ImageResult]:
    """Generate images from a text prompt.

    Args:
        prompt: Text description of the image to generate.
        provider: "openai" or "gemini".
        model: Model name override. Defaults:
            OpenAI: "gpt-5" (Responses API) or "gpt-image-1.5" (Images API).
            Gemini: "gemini-2.5-flash-image".
        images: Reference images as bytes or file Paths. For OpenAI, sent as
            visual input to the Responses API. For Gemini, sent as inline parts.
        n: Number of images to generate.
        size: Image dimensions. OpenAI: "auto", "1024x1024", "1536x1024",
            "1024x1536". Gemini: ignored (use aspect_ratio).
        quality: OpenAI only — "auto", "low", "medium", "high".
        output_format: "png", "jpeg", or "webp".
        background: OpenAI only — "auto", "transparent", "opaque".
        previous_response_id: OpenAI only — chain edits with a prior response.
        on_partial: OpenAI only — callback receiving (index, image_bytes) for
            streaming partial previews.
        partial_images: OpenAI only — number of partial previews, 0-3 (default 3).
        aspect_ratio: Gemini only — "1:1", "16:9", "9:16", etc.
        image_size: Gemini only — "1K" or "2K".

    Returns:
        List of ImageResult. Usually length 1 unless n > 1.
    """
    img_bytes = _resolve_images(images)

    if provider == "openai":
        from .openai import OpenAIProvider

        prov = OpenAIProvider(model=model or "gpt-5")
        return prov.generate(
            prompt,
            images=img_bytes,
            n=n,
            size=size,
            quality=quality,
            background=background,
            output_format=output_format,
            previous_response_id=previous_response_id,
            on_partial=on_partial,
            partial_images=partial_images,
        )
    elif provider == "gemini":
        from .gemini import GeminiProvider

        prov_g = GeminiProvider(model=model or "gemini-2.5-flash-image")
        return prov_g.generate(
            prompt,
            images=img_bytes,
            n=n,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
        )
    else:
        raise ValueError(f"Unknown provider: {provider!r}")


def edit(
    prompt: str,
    *,
    images: list[bytes | Path],
    provider: Literal["openai"] = "openai",
    model: str | None = None,
    n: int = 1,
    size: str = "auto",
    quality: str = "auto",
    output_format: str = "png",
) -> list[ImageResult]:
    """Edit existing images with a text prompt.

    Currently OpenAI only. Uses the Images edit endpoint.

    Args:
        prompt: Text description of the edits to make.
        images: Source images to edit (bytes or file Paths). At least one required.
        provider: Only "openai" supported for now.
        model: Image model override (default: "gpt-image-1.5").
        n: Number of variations to generate.
        size: Image dimensions — "auto", "1024x1024", "1536x1024", "1024x1536".
        quality: "auto", "low", "medium", "high".
        output_format: "png", "jpeg", or "webp".

    Returns:
        List of ImageResult.
    """
    img_bytes = _resolve_images(images)

    if provider == "openai":
        from .openai import OpenAIProvider

        prov = OpenAIProvider(model=None, image_model=model or "gpt-image-1.5")
        return prov.edit(
            prompt,
            images=img_bytes,
            n=n,
            size=size,
            quality=quality,
            output_format=output_format,
        )
    else:
        raise ValueError(f"Unknown provider: {provider!r}")
