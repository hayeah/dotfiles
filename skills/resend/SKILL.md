---
name: resend
description: Send emails via Resend API. Use when the user wants to send an email.
---

# resend-email

CLI for sending emails via the Resend API.

## Setup

Run once before first use:

```bash
cd {baseDir} && uv tool install -e .
```

Requires API key in `~/.env.secret`:
- `RESEND_API_KEY` — Resend API key

## Send an Email

```bash
godotenv -f ~/.env.secret resend-email send \
  --to recipient@example.com \
  --subject "Hello" \
  --body "<p>Hello from Resend!</p>"
```

Options:
- `-t, --to` (required, repeatable) — recipient email address(es)
- `-s, --subject` (required) — email subject
- `-b, --body` (required) — email body (HTML supported)
- `-f, --from` — sender address (default: `onboarding@resend.dev`)

Output: prints Resend API response as JSON to stdout.

## Multiple Recipients

```bash
godotenv -f ~/.env.secret resend-email send \
  --to alice@example.com \
  --to bob@example.com \
  --subject "Team Update" \
  --body "<p>News for everyone</p>"
```

## When to Use

- User asks to send an email
- User wants to notify someone via email
- User needs to test email delivery
