---
name: cloudflare-tunnel
description: Manage Cloudflare Tunnel ingress rules and DNS records via CLI. Use when the user wants to expose a local service to the internet through a Cloudflare Tunnel.
---

# cloudflare-tunnel

CLI for managing Cloudflare Tunnel ingress rules and DNS records. One tunnel per machine, ingress rules synced from devportv2 config.

## Model

- One remotely-managed tunnel per machine, named after `$(hostname)`
- `cloudflared` connector is run via devport (configured in `devport.toml`, not by this tool)
- Ingress rules are synced from `devport ingress` output — devport.toml is the source of truth
- Each hostname gets a proxied CNAME record pointing to `<tunnel_id>.cfargotunnel.com`
- cloudflared polls for config changes from Cloudflare's edge — no restart needed after sync

## Prerequisites

- `CLOUDFLARE_API_TOKEN` in `~/.env.secret`
  - Required permissions: **Account: Cloudflare Tunnel (Edit)**, **Zone: DNS (Edit)**
- `cloudflared` installed via mise
- Domain already on Cloudflare

## Install

```bash
cd skills/cloudflare-tunnel
uv tool install -e .
```

## Usage

All commands require `CLOUDFLARE_API_TOKEN`. Use `godotenv` to load it:

```bash
# First time: create tunnel and save config (prints token)
godotenv -f ~/.env.secret cloudflare-tunnel setup

# Sync ingress rules from devport config
devport ingress | godotenv -f ~/.env.secret cloudflare-tunnel sync

# List current tunnel mappings (JSON output)
godotenv -f ~/.env.secret cloudflare-tunnel ls

# Tear down everything: tunnel, DNS records, and local config
godotenv -f ~/.env.secret cloudflare-tunnel teardown
```

## Running cloudflared

cloudflared is run independently via devport. Add to `devport.toml`:

```toml
[service.cloudflared]
cwd = "~"
command = ["cloudflared", "tunnel", "--no-autoupdate", "run", "--token", "${CLOUDFLARE_TUNNEL_TOKEN}"]
no_port = true
env_files = ["~/.env.secret"]

[service.cloudflared.health]
type = "process"
```

The token is saved in `~/.cloudflare-tunnel.json` after `setup`. Add `CLOUDFLARE_TUNNEL_TOKEN` to `~/.env.secret`.

## Commands

### `setup`

Idempotent. Creates a remotely-managed tunnel named after the hostname, initializes empty ingress, fetches and caches the connector token in `~/.cloudflare-tunnel.json`. Safe to re-run.

### `sync`

Reads the full ingress JSON from stdin (output of `devport ingress`) and:
- Replaces the tunnel's ingress rules with the desired set
- Ensures CNAME records exist for all hostnames
- Removes CNAME records for hostnames no longer in the config

### `ls`

Fetch and display current ingress rules from Cloudflare (excludes the catch-all). Output is JSON.

### `teardown`

Deletes all DNS records for ingress hostnames, deletes the tunnel, and removes `~/.cloudflare-tunnel.json`. Prompts for confirmation.

## Local State

`~/.cloudflare-tunnel.json` stores tunnel identity and token:

```json
{
  "tunnel_id": "<uuid>",
  "tunnel_name": "<hostname>",
  "account_id": "<account-id>",
  "tunnel_token": "<base64-token>"
}
```

## Quirks and Gotchas

- **Ingress updates are full PUT**: every sync fetches the full config, replaces it, and PUTs it back. Safe for single-operator use but not concurrent
- **Zone matching**: zone ID is resolved by matching the longest suffix of the FQDN against `cf.zones.list()`
- **cloudflared polls config**: remotely-managed tunnels pick up ingress changes from Cloudflare's edge automatically

## Project Structure

```
skills/cloudflare-tunnel/
  SKILL.md -> README.md
  docs/DESIGN.md
  pyproject.toml
  examples/now/        # example time server
  src/cloudflare_tunnel/
    __init__.py
    main.py          # typer CLI entrypoint
    config.py        # load/save ~/.cloudflare-tunnel.json
    tunnel.py        # Cloudflare API operations (tunnel CRUD, ingress, DNS)
```
