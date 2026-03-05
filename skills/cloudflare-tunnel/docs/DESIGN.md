# cloudflare-tunnel — Design Doc

CLI for managing Cloudflare Tunnel ingress rules and DNS records. Builds on `devport` for process supervision of `cloudflared`.

## Model

- **One tunnel per machine**, named after `$(hostname)`
- A single `cloudflared` connector runs via devport (key: `cloudflared`)
- Multiple FQDNs are served as ingress rules on that one tunnel
- Each FQDN has a corresponding proxied CNAME record pointing to `<tunnel_id>.cfargotunnel.com`
- The tunnel's ingress config on Cloudflare is the source of truth — no local tracking of DNS records

## Environment

- `CLOUDFLARE_API_TOKEN` — in `~/.env.secret`, loaded via `godotenv`
  - Required permissions: Account: Cloudflare Tunnel (Edit), Zone: DNS (Edit)
- `cloudflared` — installed via mise
- `devport` — available on PATH or at `~/go/bin/devport`

## Local State

`~/.cloudflare-tunnel.json`:

```json
{
  "tunnel_id": "<uuid>",
  "tunnel_name": "<hostname>",
  "account_id": "<account-id>"
}
```

Created by `init`. Used by all other commands. No tunnel token is persisted — it's fetched from the API when needed.

## Zone ID Resolution

Derived at runtime from the FQDN. Call `cf.zones.list()` and match the longest suffix. For example, `now.yohoward.com` matches zone `yohoward.com`.

## Account ID Resolution

Set during `init`. Look up via `cf.accounts.list()`, or fall back to deriving from a zone (`cf.zones.get().account.id`) if the token lacks Account:Read.

## CLI Commands

### `cloudflare-tunnel setup`

Idempotent — ensures tunnel exists and cloudflared is running.

- If `~/.cloudflare-tunnel.json` exists, load it (tunnel already created)
- Otherwise:
  - Look up account ID
  - Create a remotely-managed tunnel named `$(hostname)` with `config_src="cloudflare"`
  - Initialize with empty ingress (just the catch-all `http_status:404`)
  - Save tunnel ID, tunnel name, and account ID to `~/.cloudflare-tunnel.json`
- Fetch the tunnel token from the API
- Ensure `cloudflared` is running via devport:
  - `devport run --no-port --key cloudflared -- <cloudflared-path> tunnel --no-autoupdate run --token <TOKEN>`
  - devport's `run` is already idempotent — if the service is already running, it prints existing info and exits

Safe to re-run at any time.

### `cloudflare-tunnel set <fqdn> <port|hashid>`

Add or update a tunnel mapping.

- If argument is a hashid (not a number), resolve it to a port via `devport ls` (parse JSON, match by hashid prefix)
- Fetch current tunnel ingress config
- Add/update the ingress rule for `<fqdn>` → `http://localhost:<port>`
- Always keep the catch-all `http_status:404` as the last rule
- Push updated config via API
- Look up zone ID from FQDN
- Create a proxied CNAME record (`<fqdn>` → `<tunnel_id>.cfargotunnel.com`)
  - If CNAME already exists, update it (idempotent)
- Restart cloudflared via `devport restart cloudflared` (to pick up new config)

### `cloudflare-tunnel unset <fqdn>`

Remove a tunnel mapping.

- Fetch current tunnel ingress config
- Remove the ingress rule matching `<fqdn>`
- Push updated config via API
- Look up zone ID from FQDN
- Find and delete the CNAME record for `<fqdn>` where content matches `<tunnel_id>.cfargotunnel.com`
- Restart cloudflared

### `cloudflare-tunnel ls`

List current tunnel mappings.

- Fetch tunnel ingress config from API
- Display each hostname → service mapping (excluding the catch-all)
- Output as a table or JSON

### `cloudflare-tunnel teardown`

Idempotent — ensures tunnel, DNS records, cloudflared process, and local config are all removed.

- If no config file, do nothing (already torn down)
- Order matters — delete tunnel last so we can still read its ingress config for DNS cleanup:
  - Fetch tunnel ingress config (skip if tunnel already deleted)
  - For each hostname in ingress rules, find and delete the corresponding CNAME record (skip if already gone)
  - Stop cloudflared: `devport rm cloudflared` (no-op if not running)
  - Delete the tunnel with `cascade=true` (skip if already deleted)
  - Remove `~/.cloudflare-tunnel.json`

Safe to re-run at any time. Prompt for confirmation before proceeding.

## Project Structure

```
skills/cloudflare-tunnel/
  SKILL.md
  DESIGN.md
  pyproject.toml
  src/cloudflare_tunnel/
    __init__.py
    main.py          # typer CLI entrypoint
    config.py        # load/save ~/.cloudflare-tunnel.json
    tunnel.py        # Cloudflare API operations (tunnel CRUD, ingress, DNS)
```

- CLI name: `cloudflare-tunnel`
- Python package: `cloudflare_tunnel`
- Dependencies: `typer`, `cloudflare` (Python SDK)
- Install: `uv tool install -e .`
- Run: `godotenv -f ~/.env.secret cloudflare-tunnel <command>`

## Cloudflared Path

Resolve at runtime: `~/.local/share/mise/installs/cloudflared/latest/cloudflared`, or fall back to `which cloudflared`. Mise installs the binary directly in the version directory (no `bin/` subdirectory).

## Ingress Config Update Strategy

The `configurations.update` API is a full PUT — it replaces the entire ingress config. So every `set`/`unset` must:

- Fetch current config
- Modify in memory
- PUT the full config back

This is safe for single-operator use (one CLI per tunnel). No locking needed.

## Restart Strategy

After ingress changes, `devport restart cloudflared` sends SIGHUP to the supervisor, which gracefully restarts cloudflared. This picks up the new remotely-managed config from Cloudflare's edge — cloudflared polls for config updates, but a restart ensures immediate effect.
