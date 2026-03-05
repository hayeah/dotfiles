"""Load/save ~/.cloudflare-tunnel.json."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

CONFIG_PATH = Path.home() / ".cloudflare-tunnel.json"


@dataclass
class TunnelConfig:
    tunnel_id: str
    tunnel_name: str
    account_id: str

    def save(self) -> None:
        CONFIG_PATH.write_text(
            json.dumps(
                {
                    "tunnel_id": self.tunnel_id,
                    "tunnel_name": self.tunnel_name,
                    "account_id": self.account_id,
                },
                indent=2,
            )
            + "\n"
        )

    @staticmethod
    def load() -> TunnelConfig | None:
        if not CONFIG_PATH.exists():
            return None
        data = json.loads(CONFIG_PATH.read_text())
        return TunnelConfig(
            tunnel_id=data["tunnel_id"],
            tunnel_name=data["tunnel_name"],
            account_id=data["account_id"],
        )

    @staticmethod
    def load_or_die() -> TunnelConfig:
        cfg = TunnelConfig.load()
        if cfg is None:
            raise SystemExit("No tunnel configured. Run 'cloudflare-tunnel setup' first.")
        return cfg

    @staticmethod
    def remove() -> None:
        CONFIG_PATH.unlink(missing_ok=True)
