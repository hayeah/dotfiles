"""telegram - Send Telegram messages and files via bot API."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx
import typer

app = typer.Typer(invoke_without_command=True, help="Send Telegram messages and files via bot API.")

# Telegram sendMessage limit is 4096 chars
MAX_MESSAGE_LEN = 4096


def _config() -> tuple[str, str]:
    """Return (bot_token, chat_id) from environment."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHATID", "")
    if not token:
        typer.echo("TELEGRAM_BOT_TOKEN not set", err=True)
        raise typer.Exit(1)
    if not chat_id:
        typer.echo("TELEGRAM_CHATID not set", err=True)
        raise typer.Exit(1)
    return token, chat_id


def _api_url(token: str, method: str) -> str:
    return f"https://api.telegram.org/bot{token}/{method}"


def send_text(
    client: httpx.Client,
    token: str,
    chat_id: str,
    text: str,
    *,
    link_preview: bool = True,
    parse_mode: str | None = None,
    reply_markup: dict | None = None,
) -> int | None:
    """Send a text message, chunking if necessary. Returns last message_id."""
    import json as _json

    message_id: int | None = None
    chunks = _chunk_text(text)
    for i, chunk in enumerate(chunks):
        payload: dict[str, object] = {"chat_id": chat_id, "text": chunk}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if not link_preview:
            payload["disable_web_page_preview"] = True
        if reply_markup and i == len(chunks) - 1:
            payload["reply_markup"] = _json.dumps(reply_markup)
        resp = client.post(
            _api_url(token, "sendMessage"),
            data=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        result = data.get("result", {})
        if isinstance(result, dict):
            message_id = result.get("message_id")
    return message_id


def _chunk_text(text: str) -> list[str]:
    """Split text into chunks that fit within Telegram's limit."""
    if len(text) <= MAX_MESSAGE_LEN:
        return [text]
    chunks: list[str] = []
    while text:
        if len(text) <= MAX_MESSAGE_LEN:
            chunks.append(text)
            break
        cut = text[:MAX_MESSAGE_LEN].rfind("\n")
        if cut <= 0:
            cut = MAX_MESSAGE_LEN
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return chunks


def send_file(
    client: httpx.Client,
    token: str,
    chat_id: str,
    path: Path,
    caption: str | None,
) -> None:
    """Send a file as photo or document based on extension."""
    suffix = path.suffix.lower()
    if suffix in (".png", ".jpg", ".jpeg"):
        method = "sendPhoto"
        field = "photo"
    else:
        method = "sendDocument"
        field = "document"

    data: dict[str, str] = {"chat_id": chat_id}
    if caption:
        data["caption"] = caption[:1024]

    with open(path, "rb") as f:
        resp = client.post(
            _api_url(token, method),
            data=data,
            files={field: (path.name, f)},
        )
        resp.raise_for_status()


@app.callback()
def send(
    message: list[str] = typer.Option(
        [],
        "-m",
        help="Message lines (repeatable, joined with newlines)",
    ),
    input_files: list[Path] = typer.Option(
        [],
        "-i",
        help="Files to send (text pasted as message, images as photos)",
    ),
    stdin: bool = typer.Option(False, "--stdin", help="Read message text from stdin"),
    markdown: bool = typer.Option(False, "--markdown", help="Parse message as MarkdownV2"),
) -> None:
    """Send messages and files to Telegram."""
    if not message and not input_files and not stdin:
        return

    token, chat_id = _config()

    parts: list[str] = []
    if message:
        parts.append("\n".join(message))
    if stdin:
        parts.append(sys.stdin.read())

    text_files: list[Path] = []
    media_files: list[Path] = []
    for p in input_files:
        if not p.exists():
            typer.echo(f"File not found: {p}", err=True)
            raise typer.Exit(1)
        suffix = p.suffix.lower()
        if suffix in (".png", ".jpg", ".jpeg"):
            media_files.append(p)
        else:
            text_files.append(p)

    for p in text_files:
        parts.append(p.read_text())

    combined_text = "\n".join(parts).strip() if parts else ""

    if not combined_text and not media_files:
        typer.echo("Nothing to send. Use -m, -i, or --stdin.", err=True)
        raise typer.Exit(1)

    with httpx.Client(timeout=30) as client:
        pm = "MarkdownV2" if markdown else None
        if combined_text:
            send_text(client, token, chat_id, combined_text, parse_mode=pm)

        for p in media_files:
            caption = combined_text[:1024] if combined_text and not parts else None
            send_file(client, token, chat_id, p, caption)

    typer.echo("Sent.")
