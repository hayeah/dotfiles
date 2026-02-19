
## Install Tools

- Prefer mise > homebrew when installing tools.
- For Python, use `uv` to install packages and run CLI tools.
- For npm/TypeScript, use `bunx` to install packages and run CLI tools.
  - Fall back to pnpm if bunx doesn't work.

## Markdown Style

- Avoid numbering in lists — use plain `-` bullets
- Avoid numbering in markdown headings — use descriptive text only

## Git Repos

- Put GitHub repos in `~/github.com/<user>/<repo>`
- Prefer `git-quick-clone` skill to create partial clones for open source projects.
- On personal projects `(~/github.com/hayeah/*)`, you can use `push --force-with-lease` to update remote.
- Use `gh` when you require authentication.
  - Prefer HTTPS auth.

## Env & Secrets

- API keys are stored in `~/.env.secret`.
  - Agents MUST NEVER read the secret env file.
- Use `godotenv` to load secrets and overlay with project `.env` files.
  - Later files override earlier ones.

```
godotenv -o -f ~/.env.secret,.env some_command
```

Before writing new code that needs API keys:

- Use `dotenv-ls` to check whether the required secrets are available.
- If not, propose the env var names and ask the user to fill them in before proceeding.
