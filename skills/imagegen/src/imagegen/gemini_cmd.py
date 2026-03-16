"""Gemini provider — ls and create commands using the google-genai SDK."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from google import genai
from google.genai import types
from hayeah import logger

from .attachments import load_attachment

log = logger.new("imagegen")

IMAGEN_PREFIXES = ("imagen-",)
GEMINI_IMAGE_SUFFIXES = ("-image", "-image-preview")

app = typer.Typer(help="Google Gemini image generation")


def _is_image_model(model_id: str) -> bool:
    name = model_id.removeprefix("models/")
    if any(name.startswith(p) for p in IMAGEN_PREFIXES):
        return True
    if any(name.endswith(s) for s in GEMINI_IMAGE_SUFFIXES):
        return True
    return False


def _is_imagen_model(model: str) -> bool:
    return any(model.startswith(p) for p in IMAGEN_PREFIXES)


class GeminiGenerator:
    def __init__(
        self,
        prompt: str,
        output_path: Path,
        *,
        model: str = "gemini-2.5-flash-image",
        aspect_ratio: str = "1:1",
        image_size: str = "1K",
        image_attachments: list[bytes] | None = None,
        count: int = 1,
    ):
        self.prompt = prompt
        self.output_path = output_path
        self.model = model
        self.aspect_ratio = aspect_ratio
        self.image_size = image_size
        self.image_attachments = image_attachments or []
        self.count = count

    def _run_gemini_native_once(self, client: genai.Client) -> bytes:
        contents: list = []  # type: ignore[type-arg]
        for img_bytes in self.image_attachments:
            contents.append(types.Part.from_bytes(data=img_bytes, mime_type="image/png"))
        contents.append(self.prompt)

        response = client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(
                    aspect_ratio=self.aspect_ratio,
                    image_size=self.image_size,
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

    def _run_gemini_native(self, client: genai.Client) -> list[bytes]:
        # Native Gemini models don't support numberOfImages,
        # so we call the API multiple times.
        return [self._run_gemini_native_once(client) for _ in range(self.count)]

    def _run_imagen(self, client: genai.Client) -> list[bytes]:
        response = client.models.generate_images(
            model=self.model,
            prompt=self.prompt,
            config=types.GenerateImagesConfig(
                number_of_images=self.count,
                aspect_ratio=self.aspect_ratio,
            ),
        )

        if not response.generated_images:
            raise RuntimeError("No images in Imagen response")

        images: list[bytes] = []
        for generated in response.generated_images:
            if generated.image and generated.image.image_bytes:
                images.append(generated.image.image_bytes)

        if not images:
            raise RuntimeError("No image bytes in Imagen response")

        return images

    def _output_paths(self, image_count: int) -> list[Path]:
        """Return output paths for the generated images.

        When count == 1, use the original output path as-is.
        When count > 1, use <stem>-1.png, <stem>-2.png, etc.
        """
        if image_count == 1:
            return [self.output_path]

        stem = self.output_path.stem
        suffix = self.output_path.suffix or ".png"
        parent = self.output_path.parent
        return [parent / f"{stem}-{i}{suffix}" for i in range(1, image_count + 1)]

    def run(self) -> list[Path]:
        client = genai.Client()
        log.info(
            "sending request",
            model=self.model,
            aspect_ratio=self.aspect_ratio,
            image_size=self.image_size,
            count=self.count,
        )

        if _is_imagen_model(self.model):
            all_image_bytes = self._run_imagen(client)
        else:
            all_image_bytes = self._run_gemini_native(client)

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        paths = self._output_paths(len(all_image_bytes))
        saved: list[Path] = []
        for path, image_bytes in zip(paths, all_image_bytes):
            path.write_bytes(image_bytes)
            log.info("saved image", path=str(path), bytes=len(image_bytes))
            saved.append(path)

        return saved


@app.command()
def ls() -> None:
    """List available Gemini image generation models."""
    client = genai.Client()
    image_models = sorted(
        m.name.removeprefix("models/")
        for m in client.models.list(config={"page_size": 100})
        if m.name and _is_image_model(m.name)
    )
    for model_id in image_models:
        typer.echo(model_id)


@app.command()
def create(
    prompt: list[str] = typer.Argument(..., help="Text prompt fragments (joined by newlines)"),
    output: Path = typer.Option(..., "--output", "-o", help="Output file path"),
    attach: Optional[list[Path]] = typer.Option(None, "--attach", "-a", help="Image attachments"),
    model: str = typer.Option("gemini-2.5-flash-image", "--model", help="Model to use"),
    aspect_ratio: str = typer.Option("1:1", "--aspect-ratio", help="Aspect ratio"),
    image_size: str = typer.Option("1K", "--image-size", help="Image size: 1K / 2K"),
    count: int = typer.Option(1, "--count", "-n", help="Number of images to generate (max 4)", min=1, max=4),
) -> None:
    """Generate an image using the Gemini API."""
    text_parts = list(prompt)
    image_attachments_bytes: list[bytes] = []

    for path in attach or []:
        att = load_attachment(path)
        if att.is_image:
            image_attachments_bytes.append(path.read_bytes())
        else:
            text_parts.append(att.data)

    gen = GeminiGenerator(
        prompt="\n".join(text_parts),
        output_path=output,
        model=model,
        aspect_ratio=aspect_ratio,
        image_size=image_size,
        image_attachments=image_attachments_bytes,
        count=count,
    )
    results = gen.run()
    for result in results:
        typer.echo(result)
