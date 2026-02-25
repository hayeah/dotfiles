"""OpenAI provider — ls and create commands."""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Optional

import typer
from openai import OpenAI
from openai.types.responses import Response

from .attachments import Attachment, load_attachment

log = logging.getLogger(__name__)

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

app = typer.Typer(help="OpenAI image generation")


# ---------------------------------------------------------------------------
# Responses API
# ---------------------------------------------------------------------------


class OpenAIResponses:
    def __init__(
        self,
        prompt: str,
        output_path: Path,
        *,
        model: str = "gpt-5",
        image_model: str | None = None,
        size: str = "auto",
        quality: str = "auto",
        background: str = "auto",
        image_attachments: list[Attachment] | None = None,
        previous_response_id: str | None = None,
        partial_images: int = 3,
    ):
        self.prompt = prompt
        self.output_path = output_path
        self.model = model
        self.image_model = image_model
        self.size = size
        self.quality = quality
        self.background = background
        self.image_attachments = image_attachments or []
        self.previous_response_id = previous_response_id
        self.partial_images = partial_images

    def _build_content(self) -> list[dict[str, str]]:
        content: list[dict[str, str]] = []
        content.append({"type": "input_text", "text": self.prompt})
        for att in self.image_attachments:
            content.append({"type": "input_image", "image_url": att.data_url})
        return content

    def _build_request(self) -> dict:  # type: ignore[type-arg]
        tool_config: dict = {  # type: ignore[type-arg]
            "type": "image_generation",
            "size": self.size,
            "quality": self.quality,
            "background": self.background,
        }
        if self.image_model:
            tool_config["model"] = self.image_model
        if self.partial_images > 0:
            tool_config["partial_images"] = self.partial_images

        req: dict = {  # type: ignore[type-arg]
            "model": self.model,
            "input": [{"role": "user", "content": self._build_content()}],
            "tools": [tool_config],
        }
        if self.previous_response_id:
            req["previous_response_id"] = self.previous_response_id
        return req

    def _extract_image(self, response: Response) -> bytes:
        for output in response.output:
            if output.type == "image_generation_call":
                return base64.b64decode(output.result)  # type: ignore[arg-type]
        raise RuntimeError("No image_generation_call found in response output")

    def run(self) -> tuple[Path, str]:
        """Run generation with streaming. Returns (output_path, response_id)."""
        client = OpenAI()
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        request = self._build_request()
        log.info(
            "Streaming model=%s image_model=%s partial=%d size=%s quality=%s",
            self.model,
            self.image_model or "(auto)",
            self.partial_images,
            self.size,
            self.quality,
        )

        response: Response | None = None
        with client.responses.stream(**request) as stream:
            for event in stream:
                if event.type == "response.image_generation_call.partial_image":
                    image_bytes = base64.b64decode(event.partial_image_b64)
                    self.output_path.write_bytes(image_bytes)
                    log.info(
                        "Partial %d → %s (%d bytes)",
                        event.partial_image_index, self.output_path, len(image_bytes),
                    )
                elif event.type == "response.completed":
                    response = event.response

        if response is None:
            raise RuntimeError("No response.completed event received")

        image_bytes = self._extract_image(response)
        self.output_path.write_bytes(image_bytes)
        log.info("Saved image to %s (%d bytes)", self.output_path, len(image_bytes))

        return self.output_path, response.id


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------


@app.command()
def ls() -> None:
    """List models that support image generation."""
    typer.echo("Text models (--model with --previous):")
    for m in TEXT_MODELS:
        typer.echo(f"  {m}")
    typer.echo("")
    typer.echo("Image models (--model):")
    for m in IMAGE_MODELS:
        typer.echo(f"  {m}")


@app.command()
def create(
    prompt: list[str] = typer.Argument(
        ..., help="Text prompt fragments (joined by newlines)"
    ),
    output: Path = typer.Option(
        ..., "--output", "-o", help="Output file path"
    ),
    attach: Optional[list[Path]] = typer.Option(
        None, "--attach", "-a",
        help="Attachments (images or text files)",
    ),
    model: str = typer.Option(
        "gpt-5", "--model", help="Text model"
    ),
    image_model: Optional[str] = typer.Option(
        None, "--image-model",
        help="Image model (e.g. gpt-image-1.5)",
    ),
    size: str = typer.Option("auto", "--size", help="Image size"),
    quality: str = typer.Option(
        "auto", "--quality",
        help="Quality: low / medium / high / auto",
    ),
    background: str = typer.Option(
        "auto", "--background",
        help="Background: transparent / opaque / auto",
    ),
    previous: Optional[str] = typer.Option(
        None, "--previous",
        help="Previous response ID for multi-turn editing",
    ),
    partial: int = typer.Option(
        3, "--partial",
        help="Partial image previews while streaming (0 to disable)",
    ),
) -> None:
    """Generate an image via the Responses API."""
    text_parts = list(prompt)
    image_attachments: list[Attachment] = []

    for path in attach or []:
        att = load_attachment(path)
        if att.is_image:
            image_attachments.append(att)
        else:
            text_parts.append(att.data)

    full_prompt = "\n".join(text_parts)

    gen = OpenAIResponses(
        prompt=full_prompt,
        output_path=output,
        model=model,
        image_model=image_model,
        size=size,
        quality=quality,
        background=background,
        image_attachments=image_attachments,
        previous_response_id=previous,
        partial_images=partial,
    )
    result_path, response_id = gen.run()
    typer.echo(result_path)
    typer.echo(f"response_id: {response_id}", err=True)
