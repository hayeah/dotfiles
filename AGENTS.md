## IMPORTANT: Recursive Improvements

When using a skill or tool, if you run into problems, mistakes, or ergonomic issues:

- Describe the problem and how you worked around it.
- After you are done with your task, use /mdnote to note it.
  - This helps the human review and improve your tooling and workflow.

## HOT TIPS

- `$MDNOTES_ROOT` is a memory bank of research notes, design docs, and learnings from previous work sessions. Use `qmd` to search it when asked to refer to collected notes.
- If you keep getting confused about the behaviour of a tool, quick clone the repo to study the source code.
  - Use /mdnote to produce a note.
- `~/.ctrlv` contains dumped pasteboard contents: text, files, and images. Read here if asked to check the clipboard or ctrlv.

## Temporary Files

When you need temporary files or directories, prefer NOT to use /tmp.

- Default to `$TMP_ROOT` (`$DROPBOX_ROOT/tmp`)
- Naming convention to avoid collisions:
  - `$TMP_ROOT/<date>/<msecTimestamp>-<title>`
  - Date and millisecond timestamp must be alphanumeric-sortable

## Ad-Hoc Scripting

If writing more than ~15 lines:

- Prefer writing scripts to files rather than using `-c`
  - Easier for a human to audit
  - Easier to tweak and fix
- Put ad-hoc scripts in `$TMP_ROOT` following the naming convention in "Temporary Files"
  - `$TMP_ROOT/<date>/<msecTimestamp>-<title>.<ext>`
  - To iterate on a variant, copy and edit the original
- Use uv+python for ad-hoc scripting
  - `uv run --with cloudflare python`
    - If you'd like to use a package
  - `godotenv -f ~/.env.secret uv run --with cloudflare python`
    - If you need access tokens in the script

## Dotfiles

- Make changes directly to the dotfiles repo at `~/github.com/hayeah/dotfiles`.
- Run `pymake` in `~/github.com/hayeah/dotfiles` to fully refresh.
  - It runs these tasks automatically — no need to invoke them manually:
  - `dotfiles` — symlinks `dotfiles/` into `$HOME` via `dotfile_stow.py`
  - `mise install` — installs any new tools
  - `godzkilla sync` — syncs agent skills

# Personal Peeves

Petty, I Know. But IMPORTANT for my happiness.

- When using CamelCase, preserve cap for acronyms.
  - OAuthAiModalFlow -> OAuthAIModalFlow
  - JsonApi -> JSONAPI
- The default git branch SHOULD be `master`, not `main`.

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

## Output Artifacts

When asked to produce output or artifacts, or when a human would likely want to see results:

- Produce directly to the output dir, or
- Copy interesting/relevant tmp files to the output dir

Output root dir: `$DROPBOX_ROOT/output`

- Write output to `$OUTPUT_ROOT/<date>/<taskName>` when asked
- Date should be sortable alphanumeric (e.g. `2026-03-07`)
- Create your own task name
- Reuse that path for the session
