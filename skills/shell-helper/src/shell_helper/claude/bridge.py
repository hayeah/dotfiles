"""tg-reply-bridge — poll Telegram for replies to Claude notifications, deliver to tmux."""

from __future__ import annotations

import os
import subprocess

import httpx
from hayeah import logger

from ..agent.state import AgentStateDB

log = logger.new("claude-tg-bridge")


class TGReplyBridge:
    def __init__(self, token: str):
        self.token = token
        self.db = AgentStateDB()
        self.offset = 0
        self.allowed_chat_id = os.environ.get("TELEGRAM_CHATID", "")
        self.allowed_user_id = os.environ.get("TELEGRAM_USERID", "")

    def run(self) -> None:
        if not self.allowed_chat_id:
            log.warning("TELEGRAM_CHATID not set — bridge will accept messages from any chat")
        if not self.allowed_user_id:
            log.warning("TELEGRAM_USERID not set — bridge will accept messages from any user")
        log.info(
            "bridge started, polling for replies...",
            allowed_chat_id=self.allowed_chat_id or "(any)",
            allowed_user_id=self.allowed_user_id or "(any)",
        )
        with httpx.Client(timeout=60) as client:
            self.client = client
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

    def _is_allowed(self, chat_id: int | str, user_id: int | str) -> bool:
        if self.allowed_chat_id and str(chat_id) != self.allowed_chat_id:
            return False
        if self.allowed_user_id and str(user_id) != self.allowed_user_id:
            return False
        return True

    def _handle(self, update: dict) -> None:
        if "callback_query" in update:
            cb = update["callback_query"]
            chat_id = cb.get("message", {}).get("chat", {}).get("id", "")
            user_id = cb.get("from", {}).get("id", "")
            if not self._is_allowed(chat_id, user_id):
                log.warning("rejected callback", chat_id=chat_id, user_id=user_id)
                return
            self._handle_callback(cb)
            return

        msg = update.get("message", {})
        chat_id = msg.get("chat", {}).get("id", "")
        user_id = msg.get("from", {}).get("id", "")
        if not self._is_allowed(chat_id, user_id):
            log.warning("rejected message", chat_id=chat_id, user_id=user_id)
            return

        reply_to = msg.get("reply_to_message", {})
        reply_msg_id = reply_to.get("message_id")

        if reply_msg_id:
            tmux_target = self.db.tmux_target_for(reply_msg_id)
        else:
            tmux_target = self.db.latest_tmux_target()

        if not tmux_target:
            return

        text = msg.get("text", "").strip()
        if not text:
            return

        err = self._send_to_tmux(tmux_target, text)
        if chat_id:
            if err:
                self._send_message(chat_id, err)
            else:
                self._send_typing(chat_id)

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

    def _send_typing(self, chat_id: int | str) -> None:
        try:
            self.client.post(
                f"https://api.telegram.org/bot{self.token}/sendChatAction",
                json={"chat_id": chat_id, "action": "typing"},
            )
        except Exception:
            log.exception("sendChatAction failed")

    def _remove_buttons(self, msg: dict) -> None:
        """Remove inline keyboard from the message."""
        msg_id = msg.get("message_id")
        chat_id = msg.get("chat", {}).get("id")
        if not msg_id or not chat_id:
            return

        try:
            self.client.post(
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
            self.client.post(
                f"https://api.telegram.org/bot{self.token}/answerCallbackQuery",
                data={"callback_query_id": cb_id, "text": text},
            )
        except Exception:
            log.exception("answerCallbackQuery failed")

    def _send_message(self, chat_id: int | str, text: str) -> None:
        try:
            self.client.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={"chat_id": chat_id, "text": text},
            )
        except Exception:
            log.exception("sendMessage failed")

    def _send_to_tmux(self, tmux_target: str, text: str) -> str | None:
        """Send text to tmux. Returns error message on failure, None on success."""
        log.info("delivering to tmux", target=tmux_target, text=text[:60])
        try:
            subprocess.run(
                ["tmux", "send-keys", "-t", tmux_target, "-l", text],
                check=True, timeout=5,
            )
            subprocess.run(
                ["tmux", "send-keys", "-t", tmux_target, "C-m"],
                check=True, timeout=5,
            )
            return None
        except subprocess.CalledProcessError:
            log.warning("tmux send-keys failed", target=tmux_target)
            return f"tmux send-keys failed for {tmux_target}"
        except FileNotFoundError:
            log.error("tmux not found")
            return "tmux not found"
