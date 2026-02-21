# tm — tmux session management

Aliased as `tm` via `helpers.sh`. Backed by `shell-helper tm`.

## Commands

### `tm [query]` / `tm enter [query]`

Attach to (or create) a project-named tmux session.

Unknown subcommands fall back to `enter`, so `tm foo` is equivalent to `tm enter foo`.

Resolution order:

- **No argument** — opens an fzf picker over all `~/github.com` projects
- **Directory path** — enters that project directly
- **Search string** — substring-matches against `user/repo` labels under `~/github.com`
  - Exactly one match — enters silently
  - Multiple matches — opens fzf pre-filtered with the query
  - No matches — error

### `tm which [query]`

Dry-run of `enter` — shows what a query resolves to without attaching.

### `tm select`

Interactive pane switcher. Uses fzf to list all tmux panes across sessions with a live preview of pane contents.

### `tm rename`

Renumber digit-only sessions so they count upward from 1.

## Session naming

Session names are derived in priority order:

- Path-based: `user/repo` from `~/github.com/<user>/<repo>`
- Remote-based: `user/repo` from git remote origin URL
- Project file: name from `package.json`, `Cargo.toml`, `pyproject.toml`, or `go.mod`
- Git remote: repo name from remote URL
- Fallback: directory name

Characters `.` and `:` are replaced with `-` (tmux restriction).

## Dependencies

- **tmux** — session management
- **fzf** — interactive picker (required for `enter` without args, `select`)
