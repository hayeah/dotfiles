"""cloudflare-tunnel — CLI for managing Cloudflare Tunnel ingress rules and DNS."""

from __future__ import annotations

import json
import platform
import sys

import typer

from .config import TunnelConfig
from .tunnel import (
    TunnelManager,
    create_client,
    resolve_account_id,
)

app = typer.Typer()


@app.callback()
def main() -> None:
    """Manage Cloudflare Tunnel ingress rules and DNS records."""


@app.command()
def setup() -> None:
    """Create tunnel, fetch token, and save config (idempotent)."""
    cfg = TunnelConfig.load()
    client = create_client()

    if cfg:
        typer.echo(f"Tunnel already configured: {cfg.tunnel_name} ({cfg.tunnel_id})")
    else:
        account_id = resolve_account_id(client)
        tunnel_name = platform.node()
        typer.echo(f"Creating tunnel '{tunnel_name}' ...")
        tunnel = client.zero_trust.tunnels.cloudflared.create(
            account_id=account_id,
            name=tunnel_name,
            config_src="cloudflare",
        )
        tunnel_id = tunnel.id or ""
        # Initialize with empty ingress (catch-all only)
        client.zero_trust.tunnels.cloudflared.configurations.update(
            tunnel_id,
            account_id=account_id,
            config={"ingress": [{"service": "http_status:404"}]},  # type: ignore[arg-type]
        )
        cfg = TunnelConfig(
            tunnel_id=tunnel_id,
            tunnel_name=tunnel_name,
            account_id=account_id,
        )
        cfg.save()
        typer.echo(f"Tunnel created: {tunnel_name} ({tunnel_id})")

    mgr = TunnelManager(client, cfg)
    tok = mgr.token()
    typer.echo(f"Token: {tok}")


@app.command()
def sync() -> None:
    """Sync tunnel ingress from devport config (reads JSON from stdin).

    Pipe the output of `devport ingress` into this command:

        devport ingress | godotenv -f ~/.env.secret cloudflare-tunnel sync
    """
    raw = sys.stdin.read().strip()
    if not raw:
        typer.echo("No input on stdin. Pipe devport ingress output.", err=True)
        raise typer.Exit(1)

    doc = json.loads(raw)
    desired_rules: list[dict[str, str]] = []
    for r in doc.get("ingress", []):
        hostname = r.get("hostname", "")
        service = r.get("service", "")
        if hostname:
            desired_rules.append({"hostname": hostname, "service": service})

    cfg = TunnelConfig.load_or_die()
    client = create_client()
    mgr = TunnelManager(client, cfg)

    current_rules = mgr.ingress_rules()
    current_hostnames = {r["hostname"] for r in current_rules}
    desired_hostnames = {r["hostname"] for r in desired_rules}

    # Update ingress rules
    mgr.update_ingress(desired_rules)

    # Ensure CNAME for each desired hostname
    for r in desired_rules:
        mgr.ensure_cname(r["hostname"])
        typer.echo(f"  {r['hostname']} -> {r['service']}")

    # Remove CNAME for hostnames no longer in the config
    removed = current_hostnames - desired_hostnames
    for fqdn in sorted(removed):
        mgr.delete_cname(fqdn)
        typer.echo(f"  removed {fqdn}")

    typer.echo(f"Synced {len(desired_rules)} ingress rules.")


@app.command("ls")
def ls() -> None:
    """List current tunnel mappings."""
    cfg = TunnelConfig.load_or_die()
    client = create_client()
    mgr = TunnelManager(client, cfg)

    rules = mgr.ingress_rules()
    if not rules:
        typer.echo("No ingress rules configured.")
        return
    typer.echo(json.dumps(rules, indent=2))


@app.command()
def teardown() -> None:
    """Remove tunnel, DNS records, and local config."""
    cfg = TunnelConfig.load()
    if cfg is None:
        typer.echo("No tunnel configured. Nothing to do.")
        return

    typer.confirm(
        f"This will delete tunnel '{cfg.tunnel_name}' and all its DNS records. Continue?",
        abort=True,
    )

    client = create_client()
    mgr = TunnelManager(client, cfg)

    rules = mgr.ingress_rules()
    for r in rules:
        mgr.delete_cname(r["hostname"])

    mgr.delete_tunnel()

    TunnelConfig.remove()
    typer.echo("Teardown complete.")


def run() -> None:
    app()


if __name__ == "__main__":
    run()
