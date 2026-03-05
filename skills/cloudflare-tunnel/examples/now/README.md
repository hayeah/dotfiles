# now — Current Time Server

A minimal HTTP server that returns the current UTC time. Useful as a smoke test for Cloudflare Tunnel.

## Run with devport

```bash
devport start --key now.yohoward.com -- python3 examples/now/server.py
```

This assigns a stable port (e.g. 19000) and runs the server in a tmux window.

## Map to a public FQDN

```bash
# Set up the tunnel (first time only)
godotenv -f ~/.env.secret cloudflare-tunnel setup

# Map the FQDN to the devport service by key
godotenv -f ~/.env.secret cloudflare-tunnel set now.yohoward.com now.
```

The `set` command accepts a devport hashid prefix. Since the key is `now.yohoward.com`, its hashid (e.g. `30e`) or any unique prefix works. It resolves to the assigned port automatically.

## Verify

```bash
curl https://now.yohoward.com/
# Current time: 2026-03-05T13:17:06.376028+00:00
```
