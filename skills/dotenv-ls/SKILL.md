---
name: dotenv-ls
description: List env var names from .env files without exposing values. Use when the user wants to see which env vars are defined across their dotenv files.
---

# dotenv-ls

List env var names from `.env` files without exposing values. Later files override earlier ones.

## Usage

```bash
# List vars from a single file
dotenv-ls .env

# List vars from multiple files (later overrides earlier)
dotenv-ls ~/.env.secret .env

# Output format: filepath: VAR_NAME
~/.env.secret: ANTHROPIC_API_KEY
~/.env.secret: GITHUB_TOKEN
.env: DATABASE_URL
.env: GITHUB_TOKEN
```

## Notes

- Only prints variable names, never values
- Later files override earlier ones (last writer wins)
- Supports `export` prefix, quoted values, comments
