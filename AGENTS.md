
## Dotfiles

- Use chezmoi to manage dotfiles.
- Make changes directly to the chezmoi repo at `~/github.com/hayeah/dotfiles`.
- Run chezmoi apply when you make changes.

# Personal Peeves

Petty, I Know. But IMPORTANT for my happiness.

- When using CamelCase, preserve cap for acronyms.
  - OAuthAiModalFlow -> OAuthAIModalFlow
  - JsonApi -> JSONAPI
- The default git branch SHOULD be `master`, not `main`.

## Research Notes

Notes are kept in iCloud Obsidian: `OB_PATH=~/Library/Mobile Documents/iCloud~md~obsidian/Documents`

- Create a folder per research topic: `$OB_PATH/<topic>`
- List `$OB_PATH` to find existing topics.

When researching a code library:

- Prefer cloning the repo over web search.
- Use the git-quick-clone skill to clone to `~/<host>/<user>/<repo>`.

When working in project repos (`~/<host>/<user>/<repo>`):

- Put notes in `$OB_PATH/<host>/<user>/<repo>`.
  - Symlink this directory as `.obnotes/` in the repo.

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
