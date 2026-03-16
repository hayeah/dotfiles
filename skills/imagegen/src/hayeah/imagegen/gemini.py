"""Google Gemini/Imagen image generation.

Auto-detects model family:
- Gemini native models (e.g. "gemini-2.5-flash-image") use generate_content.
- Imagen models (e.g. "imagen-4.0-generate-001") use generate_images.

Quick start:
    from hayeah.imagegen.gemini import GeminiProvider
    p = GeminiProvider()
    p.generate("a cat wearing a top hat")[0].save("cat.png")
"""

from __future__ import annotations

__all__ = ["GeminiProvider"]

from google import genai
from google.genai import types
from hayeah.core import logger

from . import ImageResult

log = logger.new("imagegen")

IMAGEN_PREFIXES = ("imagen-",)
GEMINI_IMAGE_SUFFIXES = ("-image", "-image-preview")


def is_image_model(model_id: str) -> bool:
    """Check if a model ID is an image generation model."""
    name = model_id.removeprefix("models/")
    if any(name.startswith(p) for p in IMAGEN_PREFIXES):
        return True
    if any(name.endswith(s) for s in GEMINI_IMAGE_SUFFIXES):
        return True
    return False


def is_imagen_model(model: str) -> bool:
    """Check if a model is an Imagen model (vs native Gemini)."""
    return any(model.startswith(p) for p in IMAGEN_PREFIXES)


# ---------------------------------------------------------------------------
# Provider class
# ---------------------------------------------------------------------------


class GeminiProvider:
    """Google Gemini/Imagen image generation.

    Auto-detects model family:
        - Gemini native models (e.g. "gemini-2.5-flash-image") use generate_content.
        - Imagen models (e.g. "imagen-4.0-generate-001") use generate_images.

    Args:
        model: Model name (default: "gemini-2.5-flash-image").
        client: Inject a genai.Client. Created automatically if None.
    """

    def __init__(
        self,
        *,
        model: str = "gemini-2.5-flash-image",
        client: genai.Client | None = None,
    ):
        self.model = model
        self._client = client

    @property
    def client(self) -> genai.Client:
        if self._client is None:
            self._client = genai.Client()
        return self._client

    def generate(
        self,
        prompt: str,
        *,
        images: list[bytes] | None = None,
        n: int = 1,
        aspect_ratio: str = "1:1",
        image_size: str = "1K",
    ) -> list[ImageResult]:
        """Generate images from a text prompt.

        Args:
            prompt: Text description of the image.
            images: Reference images as raw bytes.
            n: Number of images to generate (max 4).
            aspect_ratio: "1:1", "16:9", "9:16", etc.
            image_size: "1K" or "2K".
        """
        log.info(
            "sending request",
            model=self.model,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
            count=n,
        )

        if is_imagen_model(self.model):
            all_image_bytes = self._run_imagen(n=n, prompt=prompt, aspect_ratio=aspect_ratio)
        else:
            all_image_bytes = self._run_gemini_native(
                prompt=prompt,
                images=images or [],
                n=n,
                aspect_ratio=aspect_ratio,
                image_size=image_size,
            )

        return [
            ImageResult(data=data, format="png", metadata={"model": self.model})
            for data in all_image_bytes
        ]

    def list_models(self) -> list[str]:
        """List available image generation models."""
        return sorted(
            m.name.removeprefix("models/")
            for m in self.client.models.list(config={"page_size": 100})
            if m.name and is_image_model(m.name)
        )

    def _run_gemini_native_once(
        self,
        prompt: str,
        images: list[bytes],
        aspect_ratio: str,
        image_size: str,
    ) -> bytes:
        contents: list = []  # type: ignore[type-arg]
        for img_bytes in images:
            contents.append(types.Part.from_bytes(data=img_bytes, mime_type="image/png"))
        contents.append(prompt)

        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(
                    aspect_ratio=aspect_ratio,
                    image_size=image_size,
                ),
            ),
        )

        if not response.candidates:
            raise RuntimeError("No candidates in Gemini response")

        content = response.candidates[0].content
        if not content or not content.parts:
            raise RuntimeError("No parts in Gemini response")

        for part in content.parts:
            if part.inline_data and part.inline_data.data:
                return bytes(part.inline_data.data)

        raise RuntimeError("No image data found in Gemini response")

    def _run_gemini_native(
        self,
        prompt: str,
        images: list[bytes],
        n: int,
        aspect_ratio: str,
        image_size: str,
    ) -> list[bytes]:
        return [
            self._run_gemini_native_once(prompt, images, aspect_ratio, image_size)
            for _ in range(n)
        ]

    def _run_imagen(
        self,
        prompt: str,
        n: int,
        aspect_ratio: str,
    ) -> list[bytes]:
        response = self.client.models.generate_images(
            model=self.model,
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=n,
                aspect_ratio=aspect_ratio,
            ),
        )

        if not response.generated_images:
            raise RuntimeError("No images in Imagen response")

        result: list[bytes] = []
        for generated in response.generated_images:
            if generated.image and generated.image.image_bytes:
                result.append(generated.image.image_bytes)

        if not result:
            raise RuntimeError("No image bytes in Imagen response")

        return result
