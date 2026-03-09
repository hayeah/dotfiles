"""Cloudflare API operations: tunnel CRUD, ingress config, DNS."""

from __future__ import annotations

import os

from cloudflare import Cloudflare
from hayeah import logger

from .config import TunnelConfig

log = logger.new("cloudflare-tunnel")


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
        log.info("updated ingress config", rules=len(rules))

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
                log.info("updated cname", fqdn=fqdn, target=target)
                return
        self.cf.dns.records.create(
            zone_id=zone_id,
            type="CNAME",
            name=fqdn,
            content=target,
            proxied=True,
        )
        log.info("created cname", fqdn=fqdn, target=target)

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
                log.info("deleted cname", fqdn=fqdn)
                return
        log.info("no matching cname found", fqdn=fqdn)

    # -- Tunnel token --

    def token(self) -> str:
        """Get tunnel token. Uses cached value from config, falls back to API."""
        if self.config.tunnel_token:
            return self.config.tunnel_token
        tok = self.cf.zero_trust.tunnels.cloudflared.token.get(
            self.tunnel_id, account_id=self.account_id
        )
        self.config.tunnel_token = tok
        self.config.save()
        log.info("cached tunnel token in config")
        return tok

    # -- Tunnel deletion --

    def delete_tunnel(self) -> None:
        self.cf.zero_trust.tunnels.cloudflared.delete(
            self.tunnel_id, account_id=self.account_id
        )
        log.info("deleted tunnel", tunnel_id=self.tunnel_id)


def resolve_account_id(client: Cloudflare) -> str:
    """Look up account ID from the API."""
    accounts = list(client.accounts.list())
    if not accounts:
        raise SystemExit("No accounts found. Check your CLOUDFLARE_API_TOKEN permissions.")
    return accounts[0].id


def create_client() -> Cloudflare:
    """Create a Cloudflare API client from environment."""
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    if not token:
        raise SystemExit("CLOUDFLARE_API_TOKEN not set. Use godotenv -f ~/.env.secret")
    return Cloudflare(api_token=token)
