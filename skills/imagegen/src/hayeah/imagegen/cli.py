"""imagegen CLI — thin Typer wrapper over the library API."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv

from . import ImageResult, _output_format_from_path
from .attachments import Attachment, load_attachment

ENV_SECRET = Path.home() / ".env.secret"

app = typer.Typer()

# ---------------------------------------------------------------------------
# OpenAI subcommands
# ---------------------------------------------------------------------------

openai_app = typer.Typer(help="OpenAI image generation")
app.add_typer(openai_app, name="openai")


@openai_app.command("ls")
def openai_ls() -> None:
    """List models that support image generation."""
    from .openai import IMAGE_MODELS, TEXT_MODELS

    typer.echo("Text models (--model with --previous):")
    for m in TEXT_MODELS:
        typer.echo(f"  {m}")
    typer.echo("")
    typer.echo("Image models (--model):")
    for m in IMAGE_MODELS:
        typer.echo(f"  {m}")


@openai_app.command("create")
def openai_create(
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
    from .openai import OpenAIProvider

    text_parts = list(prompt)
    image_attachments: list[Attachment] = []

    for path in attach or []:
        att = load_attachment(path)
        if att.is_image:
            image_attachments.append(att)
        else:
            text_parts.append(att.data)

    full_prompt = "\n".join(text_parts)
    fmt = _output_format_from_path(output)

    if model.lower() == "none" and edit:
        if not image_attachments:
            typer.echo("Error: --edit requires at least one image attachment (-a)")
            raise typer.Exit(1)
        provider = OpenAIProvider(model=None, image_model=image_model or "gpt-image-1.5")
        results = provider.edit(
            full_prompt,
            images=[att.path.read_bytes() for att in image_attachments],
            n=n,
            size=size,
            quality=quality,
            output_format=fmt,
        )
        _write_results(results, output, n)
    elif model.lower() == "none":
        provider = OpenAIProvider(model=None, image_model=image_model or "gpt-image-1.5")
        results = provider.generate(
            full_prompt,
            n=n,
            size=size,
            quality=quality,
            background=background,
            output_format=fmt,
        )
        _write_results(results, output, n)
    else:
        def on_partial_write(index: int, data: bytes) -> None:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(data)

        provider = OpenAIProvider(model=model, image_model=image_model or "gpt-image-1.5")
        results = provider.generate(
            full_prompt,
            image_attachments=image_attachments,
            size=size,
            quality=quality,
            background=background,
            output_format=fmt,
            previous_response_id=previous,
            on_partial=on_partial_write if partial > 0 else None,
            partial_images=partial,
        )
        for result in results:
            path = result.save(output)
            typer.echo(path)

        if results and "response_id" in results[0].metadata:
            typer.echo(f"response_id: {results[0].metadata['response_id']}", err=True)

        if output_response and results:
            json_path = output.with_suffix(".json")
            json_path.write_text(json.dumps(results[0].metadata, indent=2) + "\n")


# ---------------------------------------------------------------------------
# Gemini subcommands
# ---------------------------------------------------------------------------

gemini_app = typer.Typer(help="Google Gemini image generation")
app.add_typer(gemini_app, name="gemini")


@gemini_app.command("ls")
def gemini_ls() -> None:
    """List available Gemini image generation models."""
    from .gemini import GeminiProvider

    provider = GeminiProvider()
    for model_id in provider.list_models():
        typer.echo(model_id)


@gemini_app.command("create")
def gemini_create(
    prompt: list[str] = typer.Argument(..., help="Text prompt fragments (joined by newlines)"),
    output: Path = typer.Option(..., "--output", "-o", help="Output file path"),
    attach: Optional[list[Path]] = typer.Option(None, "--attach", "-a", help="Image attachments"),
    model: str = typer.Option("gemini-2.5-flash-image", "--model", help="Model to use"),
    aspect_ratio: str = typer.Option("1:1", "--aspect-ratio", help="Aspect ratio"),
    image_size: str = typer.Option("1K", "--image-size", help="Image size: 1K / 2K"),
    count: int = typer.Option(1, "--count", "-n", help="Number of images to generate (max 4)", min=1, max=4),
) -> None:
    """Generate an image using the Gemini API."""
    from .gemini import GeminiProvider

    text_parts = list(prompt)
    image_bytes_list: list[bytes] = []

    for path in attach or []:
        att = load_attachment(path)
        if att.is_image:
            image_bytes_list.append(path.read_bytes())
        else:
            text_parts.append(att.data)

    provider = GeminiProvider(model=model)
    results = provider.generate(
        "\n".join(text_parts),
        images=image_bytes_list or None,
        n=count,
        aspect_ratio=aspect_ratio,
        image_size=image_size,
    )
    _write_results(results, output, len(results))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_results(results: list[ImageResult], output: Path, n: int) -> None:
    """Save results to disk and echo paths."""
    for i, result in enumerate(results):
        if n == 1:
            path = output
        else:
            path = output.with_stem(f"{output.stem}-{i + 1}")
        result.save(path)
        typer.echo(path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


@app.callback()
def main() -> None:
    """AI image generation CLI. Use a provider subcommand: openai or gemini."""
    if ENV_SECRET.exists():
        load_dotenv(ENV_SECRET)


def run() -> None:
    app()


if __name__ == "__main__":
    run()
