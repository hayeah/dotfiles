"""OpenAI provider — ls and create commands."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any, Optional

import typer
from hayeah import logger
from openai import OpenAI
from openai.types.responses import Response

from .attachments import Attachment, load_attachment

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

    def _output_format(self) -> str:
        """Infer output format from file extension."""
        ext_map = {".png": "png", ".webp": "webp", ".jpg": "jpeg", ".jpeg": "jpeg"}
        return ext_map.get(self.output_path.suffix.lower(), "png")

    def _build_request(self) -> dict:  # type: ignore[type-arg]
        tool_config: dict = {  # type: ignore[type-arg]
            "type": "image_generation",
            "size": self.size,
            "quality": self.quality,
            "background": self.background,
            "output_format": self._output_format(),
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

    def response_metadata(self, response: Response) -> dict[str, Any]:
        """Dump the raw response, stripping base64 image data."""
        data = response.model_dump()
        # Strip base64 image results from output items
        for item in data.get("output", []):
            if item.get("type") == "image_generation_call" and item.get("result"):
                item["result"] = f"<{len(item['result'])} chars base64>"
        # Strip base64 payload from input image URLs, keep the data:mime prefix
        for item in data.get("input", []):
            if isinstance(item, dict):
                for content in item.get("content", []):
                    if isinstance(content, dict) and content.get("type") == "input_image":
                        url = content.get("image_url", "")
                        if isinstance(url, str) and url.startswith("data:"):
                            # Keep "data:image/jpeg;base64," prefix, strip the data
                            prefix = url.split(",", 1)[0]
                            content["image_url"] = f"{prefix},<base64 omitted>"
        return data

    def run(self) -> tuple[Path, Response]:
        """Run generation with streaming. Returns (output_path, response)."""
        client = OpenAI()
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        request = self._build_request()
        log.info(
            "streaming",
            model=self.model,
            image_model=self.image_model or "(auto)",
            partial=self.partial_images,
            size=self.size,
            quality=self.quality,
        )

        response: Response | None = None
        with client.responses.stream(**request) as stream:
            for event in stream:
                if event.type == "response.image_generation_call.partial_image":
                    image_bytes = base64.b64decode(event.partial_image_b64)
                    self.output_path.write_bytes(image_bytes)
                    log.info(
                        "partial image",
                        index=event.partial_image_index,
                        path=str(self.output_path),
                        bytes=len(image_bytes),
                    )
                elif event.type == "response.completed":
                    response = event.response

        if response is None:
            raise RuntimeError("No response.completed event received")

        image_bytes = self._extract_image(response)
        self.output_path.write_bytes(image_bytes)
        log.info("saved image", path=str(self.output_path), bytes=len(image_bytes))

        return self.output_path, response


# ---------------------------------------------------------------------------
# Images API (direct, no text model)
# ---------------------------------------------------------------------------


class OpenAIImages:
    """Call the Images API directly — no text model, no prompt rewriting."""

    def __init__(
        self,
        prompt: str,
        output_path: Path,
        *,
        image_model: str = "gpt-image-1.5",
        size: str = "auto",
        quality: str = "auto",
        background: str = "auto",
        n: int = 1,
    ):
        self.prompt = prompt
        self.output_path = output_path
        self.image_model = image_model
        self.size = size
        self.quality = quality
        self.background = background
        self.n = n

    def _output_format(self) -> str:
        ext_map = {".png": "png", ".webp": "webp", ".jpg": "jpeg", ".jpeg": "jpeg"}
        return ext_map.get(self.output_path.suffix.lower(), "png")

    def run(self) -> list[Path]:
        """Generate images. Returns list of output paths."""
        client = OpenAI()
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        log.info(
            "images_api",
            model=self.image_model,
            n=self.n,
            size=self.size,
            quality=self.quality,
        )

        result = client.images.generate(
            model=self.image_model,
            prompt=self.prompt,
            n=self.n,
            size=self.size,  # type: ignore[arg-type]
            quality=self.quality,  # type: ignore[arg-type]
            background=self.background,  # type: ignore[arg-type]
            output_format=self._output_format(),  # type: ignore[arg-type]
        )

        paths: list[Path] = []
        for i, image in enumerate(result.data):
            if self.n == 1:
                path = self.output_path
            else:
                stem = self.output_path.stem
                path = self.output_path.with_stem(f"{stem}-{i + 1}")

            image_bytes = base64.b64decode(image.b64_json)  # type: ignore[arg-type]
            path.write_bytes(image_bytes)
            log.info("saved image", path=str(path), bytes=len(image_bytes))
            paths.append(path)

        return paths

    def response_metadata(self, result: Any) -> dict[str, Any]:
        """Dump the ImagesResponse, stripping base64 image data."""
        data = result.model_dump() if hasattr(result, "model_dump") else dict(result)
        for image in data.get("data", []):
            if image.get("b64_json"):
                image["b64_json"] = f"<{len(image['b64_json'])} chars base64>"
        return data


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
        "gpt-5", "--model",
        help="Text model (use 'none' to call image model directly via Images API)",
    ),
    image_model: Optional[str] = typer.Option(
        None, "--image-model",
        help="Image model (e.g. gpt-image-1.5)",
    ),
    n: int = typer.Option(
        1, "-n",
        help="Number of images (only with --model none, Images API)",
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
    edit: bool = typer.Option(
        False, "--edit",
        help="Use Images edit endpoint (requires --model none and -a image)",
    ),
    output_response: bool = typer.Option(
        False, "--output-response",
        help="Write response metadata to a .json sidecar file",
    ),
) -> None:
    """Generate an image via the Responses API, or directly via Images API with --model none."""
    text_parts = list(prompt)
    image_attachments: list[Attachment] = []

    for path in attach or []:
        att = load_attachment(path)
        if att.is_image:
            image_attachments.append(att)
        else:
            text_parts.append(att.data)

    full_prompt = "\n".join(text_parts)

    if model.lower() == "none" and edit:
        if not image_attachments:
            typer.echo("Error: --edit requires at least one image attachment (-a)")
            raise typer.Exit(1)
        _edit_images_api(
            prompt=full_prompt,
            output=output,
            image_model=image_model or "gpt-image-1.5",
            image_paths=[att.path for att in image_attachments],
            n=n,
            size=size,
            quality=quality,
            output_response=output_response,
        )
    elif model.lower() == "none":
        _create_images_api(
            prompt=full_prompt,
            output=output,
            image_model=image_model or "gpt-image-1.5",
            n=n,
            size=size,
            quality=quality,
            background=background,
            output_response=output_response,
        )
    else:
        _create_responses_api(
            prompt=full_prompt,
            output=output,
            model=model,
            image_model=image_model,
            size=size,
            quality=quality,
            background=background,
            image_attachments=image_attachments,
            previous=previous,
            partial=partial,
            output_response=output_response,
        )


def _create_responses_api(
    *,
    prompt: str,
    output: Path,
    model: str,
    image_model: str | None,
    size: str,
    quality: str,
    background: str,
    image_attachments: list[Attachment],
    previous: str | None,
    partial: int,
    output_response: bool,
) -> None:
    gen = OpenAIResponses(
        prompt=prompt,
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
    result_path, response = gen.run()

    if output_response:
        meta = gen.response_metadata(response)
        json_path = result_path.with_suffix(".json")
        json_path.write_text(json.dumps(meta, indent=2) + "\n")
        log.info("wrote_response", path=str(json_path))

    typer.echo(result_path)
    typer.echo(f"response_id: {response.id}", err=True)


def _create_images_api(
    *,
    prompt: str,
    output: Path,
    image_model: str,
    n: int,
    size: str,
    quality: str,
    background: str,
    output_response: bool,
) -> None:
    gen = OpenAIImages(
        prompt=prompt,
        output_path=output,
        image_model=image_model,
        n=n,
        size=size,
        quality=quality,
        background=background,
    )

    client = OpenAI()
    gen.output_path.parent.mkdir(parents=True, exist_ok=True)

    log.info(
        "images_api",
        model=image_model,
        n=n,
        size=size,
        quality=quality,
    )

    result = client.images.generate(
        model=image_model,
        prompt=prompt,
        n=n,
        size=size,  # type: ignore[arg-type]
        quality=quality,  # type: ignore[arg-type]
        background=background,  # type: ignore[arg-type]
        output_format=gen._output_format(),  # type: ignore[arg-type]
        moderation="low",  # type: ignore[arg-type]
    )

    for i, image in enumerate(result.data):
        if n == 1:
            path = output
        else:
            path = output.with_stem(f"{output.stem}-{i + 1}")

        image_bytes = base64.b64decode(image.b64_json)  # type: ignore[arg-type]
        path.write_bytes(image_bytes)
        log.info("saved image", path=str(path), bytes=len(image_bytes))
        typer.echo(path)

    if output_response:
        meta = gen.response_metadata(result)
        json_path = output.with_suffix(".json")
        json_path.write_text(json.dumps(meta, indent=2) + "\n")
        log.info("wrote_response", path=str(json_path))


def _edit_images_api(
    *,
    prompt: str,
    output: Path,
    image_model: str,
    image_paths: list[Path],
    n: int,
    size: str,
    quality: str,
    output_response: bool,
) -> None:
    client = OpenAI()
    output.parent.mkdir(parents=True, exist_ok=True)

    ext_map = {".png": "png", ".webp": "webp", ".jpg": "jpeg", ".jpeg": "jpeg"}
    output_format = ext_map.get(output.suffix.lower(), "png")

    # images.edit() accepts a single image or list of images as file uploads
    image_files = [open(p, "rb") for p in image_paths]
    image_input = image_files[0] if len(image_files) == 1 else image_files  # type: ignore[assignment]

    log.info(
        "images_edit",
        model=image_model,
        n=n,
        size=size,
        quality=quality,
        images=len(image_files),
    )

    result = client.images.edit(
        image=image_input,  # type: ignore[arg-type]
        prompt=prompt,
        model=image_model,
        n=n,
        size=size,  # type: ignore[arg-type]
        quality=quality,  # type: ignore[arg-type]
        output_format=output_format,  # type: ignore[arg-type]
    )

    for f in image_files:
        f.close()

    dummy = OpenAIImages(prompt=prompt, output_path=output, image_model=image_model)

    for i, image in enumerate(result.data):
        if n == 1:
            path = output
        else:
            path = output.with_stem(f"{output.stem}-{i + 1}")

        image_bytes = base64.b64decode(image.b64_json)  # type: ignore[arg-type]
        path.write_bytes(image_bytes)
        log.info("saved image", path=str(path), bytes=len(image_bytes))
        typer.echo(path)

    if output_response:
        meta = dummy.response_metadata(result)
        json_path = output.with_suffix(".json")
        json_path.write_text(json.dumps(meta, indent=2) + "\n")
        log.info("wrote_response", path=str(json_path))
