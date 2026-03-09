"""cloudflare-tunnel — CLI for managing Cloudflare Tunnel ingress rules and DNS."""

from __future__ import annotations

import json
import platform

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


@app.command("set")
def set_route(
    fqdn: str = typer.Argument(help="Fully qualified domain name"),
    port: int = typer.Argument(help="Port number"),
) -> None:
    """Add or update a tunnel mapping: FQDN -> port."""
    cfg = TunnelConfig.load_or_die()
    client = create_client()
    mgr = TunnelManager(client, cfg)

    service = f"http://localhost:{port}"
    typer.echo(f"Setting {fqdn} -> {service}")

    rules = mgr.ingress_rules()
    updated = False
    for r in rules:
        if r["hostname"] == fqdn:
            r["service"] = service
            updated = True
            break
    if not updated:
        rules.append({"hostname": fqdn, "service": service})
    mgr.update_ingress(rules)

    mgr.ensure_cname(fqdn)
    typer.echo(f"Done. {fqdn} -> {service}")


@app.command("unset")
def unset_route(
    fqdn: str = typer.Argument(help="FQDN to remove"),
) -> None:
    """Remove a tunnel mapping."""
    cfg = TunnelConfig.load_or_die()
    client = create_client()
    mgr = TunnelManager(client, cfg)

    rules = mgr.ingress_rules()
    new_rules = [r for r in rules if r["hostname"] != fqdn]
    if len(new_rules) == len(rules):
        typer.echo(f"No ingress rule found for {fqdn}")
        raise typer.Exit(1)

    mgr.update_ingress(new_rules)
    mgr.delete_cname(fqdn)
    typer.echo(f"Removed {fqdn}")


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
