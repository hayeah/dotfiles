---
name: cloudflare-tunnel
description: Manage Cloudflare Tunnel ingress rules and DNS records via CLI. Use when the user wants to expose a local service to the internet through a Cloudflare Tunnel.
---

# cloudflare-tunnel

CLI for managing Cloudflare Tunnel ingress rules and DNS records. One tunnel per machine, multiple FQDNs as ingress rules. Uses `devport` for process supervision of `cloudflared`.

## Model

- One remotely-managed tunnel per machine, named after `$(hostname)`
- A single `cloudflared` connector runs via devport (key: `cloudflared`)
- Multiple FQDNs share the tunnel as ingress rules
- Each FQDN gets a proxied CNAME record pointing to `<tunnel_id>.cfargotunnel.com`
- Cloudflare's ingress config is the source of truth

## Prerequisites

- `CLOUDFLARE_API_TOKEN` in `~/.env.secret`
  - Required permissions: **Account: Cloudflare Tunnel (Edit)**, **Zone: DNS (Edit)**
- `cloudflared` installed via mise
- `devport` on PATH or at `~/go/bin/devport`
- Domain already on Cloudflare

## Install

```bash
cd skills/cloudflare-tunnel
uv tool install -e .
```

## Usage

All commands require `CLOUDFLARE_API_TOKEN`. Use `godotenv` to load it:

```bash
# First time: create tunnel and start cloudflared
godotenv -f ~/.env.secret cloudflare-tunnel setup

# Expose a local port as a public FQDN
godotenv -f ~/.env.secret cloudflare-tunnel set app.example.com 8080

# Expose a devport service by hashid (resolves to its port)
godotenv -f ~/.env.secret cloudflare-tunnel set app.example.com b7d

# List current tunnel mappings (JSON output)
godotenv -f ~/.env.secret cloudflare-tunnel ls

# Remove a mapping (deletes ingress rule and CNAME)
godotenv -f ~/.env.secret cloudflare-tunnel unset app.example.com

# Print the tunnel connector token
godotenv -f ~/.env.secret cloudflare-tunnel token

# Tear down everything: tunnel, DNS records, cloudflared, local config
godotenv -f ~/.env.secret cloudflare-tunnel teardown
```

## Commands

### `setup`

Idempotent. Creates a remotely-managed tunnel named after the hostname, initializes empty ingress, saves config to `~/.cloudflare-tunnel.json`, and starts `cloudflared` via `devport start`. Safe to re-run.

### `set <fqdn> <port|hashid>`

Add or update a tunnel mapping. If the second argument is not a number, it's treated as a devport hashid and resolved to a port via `devport ls`. Creates/updates the CNAME DNS record and restarts cloudflared.

### `unset <fqdn>`

Remove the ingress rule and CNAME record for the given FQDN. Restarts cloudflared.

### `ls`

Fetch and display current ingress rules from Cloudflare (excludes the catch-all). Output is JSON.

### `teardown`

Deletes all DNS records for ingress hostnames, stops cloudflared via devport, deletes the tunnel, and removes `~/.cloudflare-tunnel.json`. Prompts for confirmation. Idempotent.

### `token`

Print the tunnel connector token (fetched from API, not stored locally).

## Local State

`~/.cloudflare-tunnel.json` stores tunnel identity:

```json
{
  "tunnel_id": "<uuid>",
  "tunnel_name": "<hostname>",
  "account_id": "<account-id>"
}
```

Created by `setup`. No tunnel token is persisted — it's fetched from the API each time.

## Quirks and Gotchas

- **devport restart takes hash prefix, not key**: internally, the CLI looks up the cloudflared service's hashid from `devport ls` before calling `devport restart <hashid>`
- **cloudflared path**: resolved at runtime from `~/.local/share/mise/installs/cloudflared/latest/cloudflared`, falling back to `which cloudflared`. Mise installs the binary directly in the version directory (no `bin/` subdirectory)
- **Ingress updates are full PUT**: every `set`/`unset` fetches the full config, modifies in memory, and PUTs it back. Safe for single-operator use but not concurrent
- **Account ID fallback**: if the API token lacks Account:Read, account ID is derived from a zone (`cf.zones.get().account.id`)
- **Zone matching**: zone ID is resolved by matching the longest suffix of the FQDN against `cf.zones.list()`
- **cloudflared polls config**: remotely-managed tunnels pick up config changes eventually, but `devport restart` ensures immediate effect

## Project Structure

```
skills/cloudflare-tunnel/
  SKILL.md -> README.md
  DESIGN.md
  pyproject.toml
  src/cloudflare_tunnel/
    __init__.py
    main.py          # typer CLI entrypoint
    config.py        # load/save ~/.cloudflare-tunnel.json
    tunnel.py        # Cloudflare API operations (tunnel CRUD, ingress, DNS)
    log.py           # logging setup
```
