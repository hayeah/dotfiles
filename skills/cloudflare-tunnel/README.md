---
name: cloudflare-tunnel
description: Manage Cloudflare Tunnel ingress rules and DNS records via CLI. Use when the user wants to expose a local service to the internet through a Cloudflare Tunnel.
---

# cloudflare-tunnel

CLI for managing Cloudflare Tunnel ingress rules and DNS records. One tunnel per machine, multiple FQDNs as ingress rules. Independent from devport — cloudflared is run separately via devport.yaml.

## Model

- One remotely-managed tunnel per machine, named after `$(hostname)`
- `cloudflared` connector is run via devport (configured in `devport.yaml`, not by this tool)
- Multiple FQDNs share the tunnel as ingress rules
- Each FQDN gets a proxied CNAME record pointing to `<tunnel_id>.cfargotunnel.com`
- Cloudflare's ingress config is the source of truth
- cloudflared polls for config changes from Cloudflare's edge — no restart needed after `set`/`unset`

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

# Map a local port to a public FQDN
godotenv -f ~/.env.secret cloudflare-tunnel set app.example.com 8080

# List current tunnel mappings (JSON output)
godotenv -f ~/.env.secret cloudflare-tunnel ls

# Remove a mapping (deletes ingress rule and CNAME)
godotenv -f ~/.env.secret cloudflare-tunnel unset app.example.com

# Tear down everything: tunnel, DNS records, and local config
godotenv -f ~/.env.secret cloudflare-tunnel teardown
```

## Running cloudflared

cloudflared is run independently via devport. Add to `devport.yaml`:

```yaml
- key: cloudflared
  exec: cloudflared tunnel --no-autoupdate run --token $CLOUDFLARE_TUNNEL_TOKEN
  no-port: true
  env: ~/.env.secret
```

The token is saved in `~/.cloudflare-tunnel.json` after `setup`. Add `CLOUDFLARE_TUNNEL_TOKEN` to `~/.env.secret`.

## Commands

### `setup`

Idempotent. Creates a remotely-managed tunnel named after the hostname, initializes empty ingress, fetches and caches the connector token in `~/.cloudflare-tunnel.json`. Safe to re-run.

### `set <fqdn> <port>`

Add or update a tunnel mapping. Creates/updates the CNAME DNS record. cloudflared picks up the config change automatically.

### `unset <fqdn>`

Remove the ingress rule and CNAME record for the given FQDN.

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

- **Ingress updates are full PUT**: every `set`/`unset` fetches the full config, modifies in memory, and PUTs it back. Safe for single-operator use but not concurrent
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
