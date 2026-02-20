
## Dotfiles

- Use chezmoi to manage dotfiles.
- Make changes directly to the chezmoi repo at `~/.local/share/chezmoi`.
- Run chezmoi apply when you make changes.

## Research Notes

- Keep notes in the iCloud Obsidian directory: `OB_PATH=~/Library/Mobile Documents/iCloud~md~obsidian/Documents`
- Create a folder for each research topic.
  - `$OB_PATH/<topic>`
- List `$OB_PATH` to find existing topics.

If working in a project repo:

- By convention, projects are kept in `~/<host>/<user>/<repo>`.
- Put notes in `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/<host>/<user>/<repo>`.
  - Symlink this directory as `.bnotes/` in the repo.

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
