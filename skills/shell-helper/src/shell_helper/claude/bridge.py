"""tg-reply-bridge — poll Telegram for replies to Claude notifications, deliver to tmux."""

from __future__ import annotations

import logging
import subprocess

import httpx

from .notify import NotifyDB

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
                    "allowed_updates": '["message","callback_query"]',
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
        if "callback_query" in update:
            self._handle_callback(update["callback_query"])
            return

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

        self._send_to_tmux(tmux_target, text)

    def _handle_callback(self, cb: dict) -> None:
        cb_id = cb.get("id", "")
        data = cb.get("data", "")
        msg = cb.get("message", {})
        msg_id = msg.get("message_id")

        if not msg_id:
            self._answer_callback(cb_id, "no message")
            return

        tmux_target = self.db.tmux_target_for(msg_id)
        if not tmux_target:
            self._answer_callback(cb_id, "session not found")
            return

        if data == "commit":
            self._send_to_tmux(tmux_target, "commit")
            self._remove_buttons(msg)
            self._answer_callback(cb_id, f"sent /commit → {tmux_target}")
        else:
            self._answer_callback(cb_id, f"unknown action: {data}")

    def _remove_buttons(self, msg: dict) -> None:
        """Remove inline keyboard from the message."""
        msg_id = msg.get("message_id")
        chat_id = msg.get("chat", {}).get("id")
        if not msg_id or not chat_id:
            return

        try:
            with httpx.Client(timeout=10) as client:
                client.post(
                    f"https://api.telegram.org/bot{self.token}/editMessageReplyMarkup",
                    data={
                        "chat_id": chat_id,
                        "message_id": msg_id,
                        "reply_markup": "{}",
                    },
                )
        except Exception:
            log.exception("editMessageReplyMarkup failed")

    def _answer_callback(self, cb_id: str, text: str) -> None:
        try:
            with httpx.Client(timeout=10) as client:
                client.post(
                    f"https://api.telegram.org/bot{self.token}/answerCallbackQuery",
                    data={"callback_query_id": cb_id, "text": text},
                )
        except Exception:
            log.exception("answerCallbackQuery failed")

    def _send_to_tmux(self, tmux_target: str, text: str) -> None:
        log.info("delivering to tmux %s: %s", tmux_target, text[:60])
        try:
            subprocess.run(
                ["tmux", "send-keys", "-t", tmux_target, text, "Enter"],
                check=True, timeout=5,
            )
        except subprocess.CalledProcessError:
            log.warning("tmux send-keys failed for target %s", tmux_target)
        except FileNotFoundError:
            log.error("tmux not found")


