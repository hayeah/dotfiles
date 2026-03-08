"""cloudflare-tunnel — CLI for managing Cloudflare Tunnel ingress rules and DNS."""

from __future__ import annotations

import json
import platform
import subprocess

import typer

from .config import TunnelConfig
from .tunnel import (
    TunnelManager,
    create_client,
    devport_resolve_port,
    devport_restart_cloudflared,
    devport_rm_cloudflared,
    devport_start_cloudflared,
    devport_start_service,
    resolve_account_id,
)

app = typer.Typer()


@app.callback()
def main() -> None:
    """Manage Cloudflare Tunnel ingress rules and DNS records."""


@app.command()
def setup() -> None:
    """Ensure tunnel exists and cloudflared is running (idempotent)."""
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
    token = mgr.token()
    devport_start_cloudflared(token)
    typer.echo("cloudflared is running via devport.")


@app.command("start", context_settings={"allow_extra_args": True, "allow_interspersed_args": False})
def start_service(
    ctx: typer.Context,
    fqdn: str = typer.Argument(help="FQDN to map (also used as devport key)"),
) -> None:
    """Start a service via devport and map FQDN to it.

    Usage: cloudflare-tunnel start <fqdn> -- <cmd> [args...]
    """
    if not ctx.args:
        typer.echo("Missing command after '--'. Usage: cloudflare-tunnel start <fqdn> -- <cmd>")
        raise typer.Exit(1)

    cfg = TunnelConfig.load_or_die()
    client = create_client()
    mgr = TunnelManager(client, cfg)

    # Start the service via devport (uses fqdn as key)
    port = devport_start_service(fqdn, ctx.args)
    typer.echo(f"Service started on port {port}")

    # Set up ingress + DNS
    service = f"http://localhost:{port}"
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
    devport_restart_cloudflared()
    typer.echo(f"Done. {fqdn} -> {service}")


@app.command("set")
def set_route(
    fqdn: str = typer.Argument(help="Fully qualified domain name"),
    target: str = typer.Argument(help="Port number or devport hashid"),
) -> None:
    """Add or update a tunnel mapping: FQDN -> port."""
    cfg = TunnelConfig.load_or_die()
    client = create_client()
    mgr = TunnelManager(client, cfg)

    # Resolve target to a port
    if target.isdigit():
        port = int(target)
    else:
        port = devport_resolve_port(target)

    service = f"http://localhost:{port}"
    typer.echo(f"Setting {fqdn} -> {service}")

    # Update ingress
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

    # Ensure DNS
    mgr.ensure_cname(fqdn)

    # Restart cloudflared
    devport_restart_cloudflared()
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
    devport_restart_cloudflared()
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
    """Remove tunnel, DNS records, cloudflared process, and local config."""
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

    # Clean up DNS records for all ingress hostnames
    rules = mgr.ingress_rules()
    for r in rules:
        mgr.delete_cname(r["hostname"])

    # Stop cloudflared
    devport_rm_cloudflared()

    # Delete tunnel
    mgr.delete_tunnel()

    # Remove local config
    TunnelConfig.remove()
    typer.echo("Teardown complete.")


@app.command()
def token() -> None:
    """Print the tunnel connector token."""
    cfg = TunnelConfig.load_or_die()
    client = create_client()
    mgr = TunnelManager(client, cfg)
    typer.echo(mgr.token())


def run() -> None:
    app()


if __name__ == "__main__":
    run()
