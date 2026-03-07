## Scripting HOT TIPS

- Prefer uv+python for ad-hoc scripting.
  - `uv run --with cloudflare python -c`
    - If you'd like to use a package.
  - `godotenv -f ~/.env.secret uv run --with cloudflare python -c`
    - If you need access tokens in the script.
- If you keep getting confused about the behaviour of a tool, quick clone the repo to study the source code.

## Dotfiles

- Use chezmoi to manage dotfiles.
- Make changes directly to the chezmoi repo at `~/github.com/hayeah/dotfiles`.
- Run chezmoi apply when you make changes.
- After pulling changes, run `pymake` in `~/github.com/hayeah/dotfiles` to fully refresh.
  - It runs these tasks automatically — no need to invoke them manually:
  - `chezmoi apply` — applies dotfile changes
  - `mise install` — installs any new tools
  - `godzkilla sync` — syncs agent skills

# Personal Peeves

Petty, I Know. But IMPORTANT for my happiness.

- When using CamelCase, preserve cap for acronyms.
  - OAuthAiModalFlow -> OAuthAIModalFlow
  - JsonApi -> JSONAPI
- The default git branch SHOULD be `master`, not `main`.

## Notification / Human Attention

Notify the user with voice when:

- A long-running task completes.
- You require user intervention or a response to carry on.

```
godotenv -f ~/.env.secret gosay "one sentence description of what was done"
```

## Install Tools

- Prefer mise > homebrew when installing tools.
- For Python, use `uv` to install packages and run CLI tools.
- For npm/TypeScript, use `bunx` to install packages and run CLI tools.
  - Fall back to pnpm if bunx doesn't work.
- If working with a CLI tool that we have a repo for, prefer installing in editable mode so that source changes take effect immediately.
  - Go CLI: `gobin install .` (use the `gobin` skill)
  - Python CLI: `uv tool install -e .`
  - TypeScript CLI: `pnpm link`

## General Code Style

- For complex features, avoid bags of loose functions 
  - Group related methods in a class or struct.
  - Prefer class properties over passing shared state through parameters.
- Name getters as nouns, not `get*` — e.g. `user()` not `getUser()`.

## Markdown Style

- Avoid numbering in lists — use plain `-` bullets
- Avoid numbering in markdown headings — use descriptive text only

## Git Repos

- Put GitHub repos in `~/github.com/<user>/<repo>`
- Set `GITHUB_REPOS=~` so tools default to cloning under `~/`.
  - `gobin` and `git-quick-clone` resolve repos relative to `$GITHUB_REPOS`.

```
# clones to ~/github.com/user/repo
git-quick-clone github.com/user/repo
```
- Prefer `git-quick-clone` skill to create partial clones for open source projects.
- On personal projects `(~/github.com/hayeah/*)`, you can use `push --force-with-lease` to update remote.
- Use `gh` when you require authentication.
  - Prefer HTTPS auth.
- Default to use "master" rather than "main".

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
