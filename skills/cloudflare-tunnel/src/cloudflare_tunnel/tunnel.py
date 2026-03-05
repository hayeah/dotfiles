"""Cloudflare API operations: tunnel CRUD, ingress config, DNS."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path

from cloudflare import Cloudflare

from .config import TunnelConfig

log = logging.getLogger(__name__)

MISE_CLOUDFLARED = Path.home() / ".local/share/mise/installs/cloudflared/latest/cloudflared"


class TunnelManager:
    """Manages a single Cloudflare Tunnel and its ingress/DNS."""

    def __init__(self, client: Cloudflare, config: TunnelConfig):
        self.cf = client
        self.config = config

    @property
    def tunnel_id(self) -> str:
        return self.config.tunnel_id

    @property
    def account_id(self) -> str:
        return self.config.account_id

    @property
    def tunnel_target(self) -> str:
        return f"{self.tunnel_id}.cfargotunnel.com"

    # -- Zone resolution --

    def zone_id_for_fqdn(self, fqdn: str) -> str:
        """Find the zone ID by matching the longest suffix of fqdn."""
        zones = list(self.cf.zones.list())
        best_zone_id = ""
        best_len = 0
        for z in zones:
            name = z.name or ""
            if (fqdn == name or fqdn.endswith("." + name)) and len(name) > best_len:
                best_zone_id = z.id or ""
                best_len = len(name)
        if not best_zone_id:
            raise SystemExit(f"No Cloudflare zone found for '{fqdn}'")
        return best_zone_id

    # -- Ingress config --

    def ingress_rules(self) -> list[dict[str, str]]:
        """Fetch current ingress rules (excluding catch-all)."""
        resp = self.cf.zero_trust.tunnels.cloudflared.configurations.get(
            self.tunnel_id, account_id=self.account_id
        )
        if not resp or not resp.config or not resp.config.ingress:
            return []
        rules: list[dict[str, str]] = []
        for r in resp.config.ingress:
            hostname = getattr(r, "hostname", "") or ""
            service = getattr(r, "service", "") or ""
            if not hostname:
                continue  # skip catch-all
            rules.append({"hostname": hostname, "service": service})
        return rules

    def update_ingress(self, rules: list[dict[str, str]]) -> None:
        """Push full ingress config (rules + catch-all)."""
        ingress: list[dict[str, str]] = []
        for r in rules:
            ingress.append({"hostname": r["hostname"], "service": r["service"]})
        ingress.append({"service": "http_status:404"})  # catch-all

        self.cf.zero_trust.tunnels.cloudflared.configurations.update(
            self.tunnel_id,
            account_id=self.account_id,
            config={"ingress": ingress},  # type: ignore[arg-type]
        )
        log.info("Updated ingress config with %d rule(s)", len(rules))

    # -- DNS --

    def ensure_cname(self, fqdn: str) -> None:
        """Create or update a proxied CNAME record for fqdn."""
        zone_id = self.zone_id_for_fqdn(fqdn)
        existing = list(
            self.cf.dns.records.list(zone_id=zone_id, type="CNAME", name=fqdn)
        )
        target = self.tunnel_target
        for rec in existing:
            if rec.name == fqdn:
                self.cf.dns.records.update(
                    rec.id or "",
                    zone_id=zone_id,
                    type="CNAME",
                    name=fqdn,
                    content=target,
                    proxied=True,
                )
                log.info("Updated CNAME %s -> %s", fqdn, target)
                return
        self.cf.dns.records.create(
            zone_id=zone_id,
            type="CNAME",
            name=fqdn,
            content=target,
            proxied=True,
        )
        log.info("Created CNAME %s -> %s", fqdn, target)

    def delete_cname(self, fqdn: str) -> None:
        """Delete the CNAME record for fqdn if it points to this tunnel."""
        zone_id = self.zone_id_for_fqdn(fqdn)
        target = self.tunnel_target
        records = list(
            self.cf.dns.records.list(zone_id=zone_id, type="CNAME", name=fqdn)
        )
        for rec in records:
            if rec.name == fqdn and rec.content == target:
                self.cf.dns.records.delete(rec.id or "", zone_id=zone_id)
                log.info("Deleted CNAME %s", fqdn)
                return
        log.info("No matching CNAME found for %s", fqdn)

    # -- Tunnel token --

    def token(self) -> str:
        return self.cf.zero_trust.tunnels.cloudflared.token.get(
            self.tunnel_id, account_id=self.account_id
        )

    # -- Tunnel deletion --

    def delete_tunnel(self) -> None:
        # The SDK delete doesn't support cascade query param directly,
        # so we use the raw HTTP client.
        self.cf.zero_trust.tunnels.cloudflared.delete(
            self.tunnel_id, account_id=self.account_id
        )
        log.info("Deleted tunnel %s", self.tunnel_id)


def cloudflared_path() -> str:
    """Resolve cloudflared binary path."""
    if MISE_CLOUDFLARED.exists():
        return str(MISE_CLOUDFLARED)
    which = shutil.which("cloudflared")
    if which:
        return which
    raise SystemExit("cloudflared not found. Install via: mise install cloudflared")


def devport_path() -> str:
    """Resolve devport binary path."""
    which = shutil.which("devport")
    if which:
        return which
    candidate = Path.home() / "go/bin/devport"
    if candidate.exists():
        return str(candidate)
    raise SystemExit("devport not found. Build from ~/.claude/skills/github.com_hayeah_devport")


def _devport_ls() -> list[dict]:
    """List all devport services."""
    result = subprocess.run(
        [devport_path(), "ls"],
        capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout)


def _devport_hashid_for_key(key: str) -> str:
    """Look up a devport service's hashid by key."""
    for svc in _devport_ls():
        if svc.get("key") == key:
            return svc["hashid"]
    raise SystemExit(f"No devport service found with key '{key}'")


def devport_start_cloudflared(tunnel_token: str) -> None:
    """Start cloudflared via devport in background (idempotent)."""
    cmd = [
        devport_path(),
        "start", "--no-port", "--key", "cloudflared", "--",
        cloudflared_path(),
        "tunnel", "--no-autoupdate", "run", "--token", tunnel_token,
    ]
    log.info("Running: %s", " ".join(cmd))
    subprocess.run(cmd, check=True)


def devport_start_service(key: str, cmd: list[str]) -> int:
    """Start a service via devport and return the assigned port."""
    result = subprocess.run(
        [devport_path(), "start", "--key", key, "--"] + cmd,
        capture_output=True, text=True, check=True,
    )
    info = json.loads(result.stdout)
    return int(info["port"])


def devport_restart_cloudflared() -> None:
    """Restart cloudflared via devport."""
    hashid = _devport_hashid_for_key("cloudflared")
    subprocess.run([devport_path(), "restart", hashid], check=True)


def devport_rm_cloudflared() -> None:
    """Remove cloudflared from devport (no-op if not running)."""
    try:
        hashid = _devport_hashid_for_key("cloudflared")
    except SystemExit:
        return  # not registered, nothing to do
    subprocess.run([devport_path(), "rm", hashid], check=False)


def devport_resolve_port(hashid: str) -> int:
    """Resolve a devport hashid to a port number."""
    for svc in _devport_ls():
        svc_hashid = svc.get("hashid", "")
        if svc_hashid.startswith(hashid):
            return int(svc["port"])
    raise SystemExit(f"No devport service found matching hashid '{hashid}'")


def resolve_account_id(client: Cloudflare) -> str:
    """Look up account ID. Try accounts.list first, fall back to zones."""
    accounts = list(client.accounts.list())
    if accounts:
        return accounts[0].id
    # Fall back: get account ID from a zone
    zones = list(client.zones.list())
    if not zones:
        raise SystemExit("No zones found. Cannot determine account ID.")
    zone = client.zones.get(zone_id=zones[0].id or "")
    if zone and zone.account:
        return zone.account.id
    raise SystemExit("Could not determine account ID from zones.")


def create_client() -> Cloudflare:
    """Create a Cloudflare API client from environment."""
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    if not token:
        raise SystemExit("CLOUDFLARE_API_TOKEN not set. Use godotenv -f ~/.env.secret")
    return Cloudflare(api_token=token)
