"""tg-reply-bridge — poll Telegram for replies to Claude notifications, deliver to tmux."""

from __future__ import annotations

import logging
import os
import subprocess

import httpx
import typer

from .notify import NotifyDB

app = typer.Typer(help="Telegram reply → tmux bridge.")

log = logging.getLogger(__name__)


class TGReplyBridge:
    def __init__(self, token: str):
        self.token = token
        self.db = NotifyDB()
        self.offset = 0

    def run(self) -> None:
        log.info("bridge started, polling for replies...")
        with httpx.Client(timeout=60) as client:
            while True:
                for update in self._poll(client):
                    self._handle(update)

    def _poll(self, client: httpx.Client) -> list[dict]:
        try:
            resp = client.get(
                f"https://api.telegram.org/bot{self.token}/getUpdates",
                params={
                    "offset": self.offset,
                    "timeout": 30,
                    "allowed_updates": '["message"]',
                },
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            log.exception("poll failed")
            return []

        results = data.get("result", [])
        if results:
            self.offset = results[-1]["update_id"] + 1
        return results

    def _handle(self, update: dict) -> None:
        msg = update.get("message", {})
        reply_to = msg.get("reply_to_message", {})
        reply_msg_id = reply_to.get("message_id")
        if not reply_msg_id:
            return

        tmux_target = self.db.tmux_target_for(reply_msg_id)
        if not tmux_target:
            return

        text = msg.get("text", "").strip()
        if not text:
            return

        log.info("delivering reply to tmux %s: %s", tmux_target, text[:60])
        try:
            subprocess.run(
                ["tmux", "send-keys", "-t", tmux_target, text, "Enter"],
                check=True, timeout=5,
            )
        except subprocess.CalledProcessError:
            log.warning("tmux send-keys failed for target %s", tmux_target)
        except FileNotFoundError:
            log.error("tmux not found")


@app.callback(invoke_without_command=True)
def bridge() -> None:
    """Poll Telegram for replies to Claude notifications and deliver to tmux."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        typer.echo("TELEGRAM_BOT_TOKEN not set", err=True)
        raise typer.Exit(1)

    TGReplyBridge(token).run()
