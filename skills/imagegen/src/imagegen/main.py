"""imagegen — AI image generation CLI with provider-specific subcommands."""

from __future__ import annotations

from pathlib import Path

import typer
from dotenv import load_dotenv

from .gemini_cmd import app as gemini_app
from .log import setup_logging
from .openai_cmd import app as openai_app

ENV_SECRET = Path.home() / ".env.secret"

app = typer.Typer()
app.add_typer(openai_app, name="openai")
app.add_typer(gemini_app, name="gemini")


@app.callback()
def main() -> None:
    """AI image generation CLI. Use a provider subcommand: openai or gemini."""
    if ENV_SECRET.exists():
        load_dotenv(ENV_SECRET)
    setup_logging()


def run() -> None:
    app()


if __name__ == "__main__":
    run()
