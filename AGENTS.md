
## Install Tools

- Prefer mise > homebrew when installing tools.
- For python, use `uv` to install package and run cli tools.
- For npm/typescript, use `bunx` to install package and run cli tools.
  - Fallback to pnpm if bunx doesn't work.

## Markdown Style

- Avoid numbering in lists — use plain `-` bullets
- Avoid numbering in markdown headings — use descriptive text only

## Git Repos

- Put GitHub repos in `~/github.com/<user>/<repo>`
- Prefer `git-quick-clone` skill to create partial clones for open source projects.
- On personal projects `(~/github.com/hayeah/*)`, you can use `push --force-with-lease` to update remote.
