"""OpenAI image generation provider.

Supports two APIs:
- Responses API (streaming, multi-turn, attachments) — when model is set
- Images API (direct generation/edit, no text model) — when model is None
"""

from __future__ import annotations

import base64
from collections.abc import Callable
from typing import Any

from hayeah.core import logger
from openai import OpenAI
from openai.types.responses import Response

from .attachments import Attachment

log = logger.new("imagegen")

# Text models that support the image_generation tool in the Responses API.
TEXT_MODELS = [
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
    "o3",
    "gpt-5",
    "gpt-5-nano",
    "gpt-5.2",
]

# Underlying image generation models.
IMAGE_MODELS = [
    "gpt-image-1.5",
    "gpt-image-1",
    "gpt-image-1-mini",
]


def _output_format(suffix: str) -> str:
    """Infer output format from file extension."""
    ext_map = {".png": "png", ".webp": "webp", ".jpg": "jpeg", ".jpeg": "jpeg"}
    return ext_map.get(suffix.lower(), "png")


class OpenAIProvider:
    """OpenAI image generation via Responses API or Images API.

    Merges the former OpenAIResponses and OpenAIImages classes.
    Auto-selects Responses API (streaming, multi-turn) vs Images API
    (direct, no text model) based on whether model is set.

    Args:
        model: Text model for Responses API (default: "gpt-5").
            Set to None to use Images API directly.
        image_model: Underlying image model (default: "gpt-image-1.5").
        client: Inject an OpenAI client. Created automatically if None.
    """

    def __init__(
        self,
        *,
        model: str | None = "gpt-5",
        image_model: str = "gpt-image-1.5",
        client: OpenAI | None = None,
    ):
        self.model = model
        self.image_model = image_model
        self._client = client

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI()
        return self._client

    def generate(
        self,
        prompt: str,
        *,
        images: list[bytes] | None = None,
        image_attachments: list[Attachment] | None = None,
        n: int = 1,
        size: str = "auto",
        quality: str = "auto",
        background: str = "auto",
        output_format: str = "png",
        previous_response_id: str | None = None,
        on_partial: Callable[[int, bytes], None] | None = None,
        partial_images: int = 3,
    ) -> list[ImageResult]:
        """Generate images from a text prompt.

        When self.model is set, uses the Responses API (supports streaming,
        multi-turn, attachments). When self.model is None, calls the Images
        API directly.

        Args:
            prompt: Text description of the image.
            images: Reference images as raw bytes.
            image_attachments: Reference images as Attachment objects (alternative to images).
            n: Number of images (Images API only).
            size: Image dimensions — "auto", "1024x1024", "1536x1024", "1024x1536".
            quality: "auto", "low", "medium", "high".
            background: "auto", "transparent", "opaque".
            output_format: "png", "jpeg", or "webp".
            previous_response_id: Chain edits with a prior response (Responses API only).
            on_partial: Callback for streaming partial previews (Responses API only).
            partial_images: Number of partial previews, 0-3 (Responses API only).
        """
        from . import ImageResult

        if self.model is not None:
            return self._generate_responses(
                prompt,
                image_attachments=image_attachments,
                size=size,
                quality=quality,
                background=background,
                output_format=output_format,
                previous_response_id=previous_response_id,
                on_partial=on_partial,
                partial_images=partial_images,
            )
        else:
            return self._generate_images(
                prompt,
                n=n,
                size=size,
                quality=quality,
                background=background,
                output_format=output_format,
            )

    def edit(
        self,
        prompt: str,
        *,
        images: list[bytes],
        n: int = 1,
        size: str = "auto",
        quality: str = "auto",
        output_format: str = "png",
    ) -> list[ImageResult]:
        """Edit images using the Images edit endpoint.

        Args:
            prompt: Text description of the edits.
            images: Source images as raw bytes. At least one required.
            n: Number of variations.
            size: Image dimensions.
            quality: "auto", "low", "medium", "high".
            output_format: "png", "jpeg", or "webp".
        """
        from . import ImageResult

        log.info(
            "images_edit",
            model=self.image_model,
            n=n,
            size=size,
            quality=quality,
            images=len(images),
        )

        # images.edit() accepts file-like objects
        import io

        image_files = [io.BytesIO(data) for data in images]
        image_input = image_files[0] if len(image_files) == 1 else image_files  # type: ignore[assignment]

        result = self.client.images.edit(
            image=image_input,  # type: ignore[arg-type]
            prompt=prompt,
            model=self.image_model,
            n=n,
            size=size,  # type: ignore[arg-type]
            quality=quality,  # type: ignore[arg-type]
            output_format=output_format,  # type: ignore[arg-type]
        )

        results: list[ImageResult] = []
        for image in result.data:
            image_bytes = base64.b64decode(image.b64_json)  # type: ignore[arg-type]
            results.append(ImageResult(
                data=image_bytes,
                format=output_format,
                metadata={"model": self.image_model},
            ))

        return results

    def _generate_responses(
        self,
        prompt: str,
        *,
        image_attachments: list[Attachment] | None = None,
        size: str,
        quality: str,
        background: str,
        output_format: str,
        previous_response_id: str | None,
        on_partial: Callable[[int, bytes], None] | None,
        partial_images: int,
    ) -> list[ImageResult]:
        from . import ImageResult

        content: list[dict[str, str]] = [{"type": "input_text", "text": prompt}]
        for att in image_attachments or []:
            content.append({"type": "input_image", "image_url": att.data_url})

        tool_config: dict = {  # type: ignore[type-arg]
            "type": "image_generation",
            "size": size,
            "quality": quality,
            "background": background,
            "output_format": output_format,
        }
        if self.image_model:
            tool_config["model"] = self.image_model
        if partial_images > 0:
            tool_config["partial_images"] = partial_images

        req: dict = {  # type: ignore[type-arg]
            "model": self.model,
            "input": [{"role": "user", "content": content}],
            "tools": [tool_config],
        }
        if previous_response_id:
            req["previous_response_id"] = previous_response_id

        log.info(
            "streaming",
            model=self.model,
            image_model=self.image_model or "(auto)",
            partial=partial_images,
            size=size,
            quality=quality,
        )

        response: Response | None = None
        with self.client.responses.stream(**req) as stream:
            for event in stream:
                if event.type == "response.image_generation_call.partial_image":
                    partial_bytes = base64.b64decode(event.partial_image_b64)
                    if on_partial:
                        on_partial(event.partial_image_index, partial_bytes)
                    log.info(
                        "partial image",
                        index=event.partial_image_index,
                        bytes=len(partial_bytes),
                    )
                elif event.type == "response.completed":
                    response = event.response

        if response is None:
            raise RuntimeError("No response.completed event received")

        # Extract image from response
        image_bytes: bytes | None = None
        for output in response.output:
            if output.type == "image_generation_call":
                image_bytes = base64.b64decode(output.result)  # type: ignore[arg-type]
                break

        if image_bytes is None:
            raise RuntimeError("No image_generation_call found in response output")

        metadata = self._response_metadata(response)

        return [ImageResult(
            data=image_bytes,
            format=output_format,
            metadata=metadata,
        )]

    def _generate_images(
        self,
        prompt: str,
        *,
        n: int,
        size: str,
        quality: str,
        background: str,
        output_format: str,
    ) -> list[ImageResult]:
        from . import ImageResult

        log.info(
            "images_api",
            model=self.image_model,
            n=n,
            size=size,
            quality=quality,
        )

        result = self.client.images.generate(
            model=self.image_model,
            prompt=prompt,
            n=n,
            size=size,  # type: ignore[arg-type]
            quality=quality,  # type: ignore[arg-type]
            background=background,  # type: ignore[arg-type]
            output_format=output_format,  # type: ignore[arg-type]
            moderation="low",  # type: ignore[arg-type]
        )

        results: list[ImageResult] = []
        for image in result.data:
            image_bytes = base64.b64decode(image.b64_json)  # type: ignore[arg-type]
            results.append(ImageResult(
                data=image_bytes,
                format=output_format,
                metadata={"model": self.image_model},
            ))

        return results

    @staticmethod
    def _response_metadata(response: Response) -> dict[str, Any]:
        """Extract metadata from a Response, stripping base64 image data."""
        data = response.model_dump()
        for item in data.get("output", []):
            if item.get("type") == "image_generation_call" and item.get("result"):
                item["result"] = f"<{len(item['result'])} chars base64>"
        for item in data.get("input", []):
            if isinstance(item, dict):
                for content in item.get("content", []):
                    if isinstance(content, dict) and content.get("type") == "input_image":
                        url = content.get("image_url", "")
                        if isinstance(url, str) and url.startswith("data:"):
                            prefix = url.split(",", 1)[0]
                            content["image_url"] = f"{prefix},<base64 omitted>"
        data["response_id"] = response.id
        return data
