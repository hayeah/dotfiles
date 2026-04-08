# boss CLI — design notes

Spec for the `boss` command. **Not yet implemented.** The boss skill currently inlines the spawn dance in BOSS_LOOP.md / SKILL.md. This document captures the eventual CLI shape so we can build it once we've used the inline version enough to know it's right.

## Design principle: minimal wrapping

We do **not** want a fat wrapper around agentboss. Most "what is this session doing" questions are already answered by:

- `agentboss status <session> -q`
- `agentboss output <session> -n 80`
- `agentboss send <session> "..."`
- `agentboss attach <session>`
- `agentboss ls`

We do not duplicate or rename any of those. The boss skill drives them directly using the `session` value read from `$MDNOTES_ROOT/boss/meta.json` (keyed by section slug).

The **only** thing that needs wrapping is the spawn step, because spawning a boss subagent involves four things that have to happen together and in order:

- Mint the section dir under `$MDNOTES_ROOT/boss/<date>/<HHMMSS.ms>-<slug>/`
- Lease a git worktree via `git-worktree open`
- Run `agentboss run --bg --cwd <worktree> -- claude ...` and capture the auto-generated key
- Read-modify-write `$MDNOTES_ROOT/boss/meta.json` to add the new section's entry

Doing this by hand is fiddly and error-prone (worktree path capture, JSON parsing, JSON merging). Doing it as a single command is one line.

Everything else in the workflow is already a one-liner against agentboss, `jq`, or the filesystem.

## The single command: `boss spawn`

```
boss spawn <section-header> [--base <ref>] [--from <boss-doc>] [--project <dir>]
```

Arguments:

- `<section-header>` — the exact text of the `## ` header in the boss doc, e.g. `"Add user authentication"`. Used to derive the slug and to find the section in the boss doc.
- `--base <ref>` — base ref for the worktree branch. Default: `origin/master`.
- `--from <boss-doc>` — path to BOSS.md. Default: `./BOSS.md`.
- `--project <dir>` — main repo dir (where `.worktrees/` lives). Default: cwd. The worktree is leased relative to this dir.

What it does, in order:

- Resolve the project dir, boss doc path, and base ref.
- Compute `slug = kebab(strip_checkbox(section_header))`. Reject if no matching `## ` header in the boss doc.
- Read `$MDNOTES_ROOT/boss/meta.json`. **Reject** if the slug already has an entry with a non-null `session` (the section is already running). Caller has to clear it first.
- Compute `prefix = HHMMSS.ms`, `date = YYYY-MM-DD`. The section dir is `$MDNOTES_ROOT/boss/$date/$prefix-$slug`.
- `mkdir -p` the section dir.
- Lease a worktree: `git-worktree open "$slug" --base "$base"` (in the background, capture printed worktree path).
- Spawn the agent: `agentboss run --bg --detector claude --cwd "$worktree" -- claude --dangerously-skip-permissions`. Parse the JSON; capture `key` (the auto-generated `boss-XXX`).
- Send the briefing prompt via `agentboss send "$key" "..."` — points the agent at AGENT_LOOP.md, the section dir, the worklog path, and the section header.
- Read-modify-write `$MDNOTES_ROOT/boss/meta.json`: add or replace the slug's entry with:
  ```json
  {
    "<slug>": {
      "header": "<original header text>",
      "dir": "<date>/<prefix>-<slug>",
      "worktree": "<worktree path, relative to project dir>",
      "session": "<agentboss key>",
      "spawned_at": "<ISO timestamp>"
    }
  }
  ```
  Use a tempfile + atomic rename so a crash mid-write doesn't corrupt the file.
- Print a single JSON line to stdout summarizing what was done:
  ```json
  {
    "slug": "add-user-authentication",
    "dir": "2026-04-08/143052.283-add-user-authentication",
    "section_dir": "/Users/me/Dropbox/notes/boss/2026-04-08/143052.283-add-user-authentication",
    "worktree": ".worktrees/001",
    "session": "boss-a3f",
    "tmux_target": "__agent:boss-a3f"
  }
  ```

That's all `boss spawn` does. No other subcommands.

The boss doc itself is **never modified by `boss spawn`**. The doc stays clean — the human owns it. All machine state is in `meta.json`.

## What `boss spawn` does NOT do

- It does **not** modify the boss doc. BOSS.md is owned by the human; the CLI only writes to `meta.json`.
- It does **not** wrap `attach`, `output`, `send`, `status`, `ls`, `kill`. Use agentboss directly with the `session` value from `meta.json`.
- It does **not** handle `lgtm` / merge / cleanup. The subagent runs `git-worktree lgtm` from inside its worktree when the human approves; that releases the worktree and ends its own Claude session. The boss (Claude session) clears `meta.json[<slug>].session` to `null` after.
- It refuses to spawn over a section that already has a live `session` in `meta.json`. The boss Claude session must explicitly clear it (or pass a future `--force` flag — not in v1).

## Implementation notes

- Language: Python via `uv`, matching `git-worktree`'s layout. Probably installed via `uv tool install -e ./skills/boss/cli` once the skill grows a `cli/` dir. For the initial pass it can be a single script in `skills/boss/bin/spawn`.
- Dependencies: only stdlib + `subprocess`. No need for click/typer for one command.
- `meta.json` updates must be **atomic**: write to `meta.json.tmp` in the same dir, then `os.replace()` onto `meta.json`. Read-modify-write should be done in one process — there's no concurrent writer in v1, but atomic rename is cheap insurance against crashes mid-write.
- Slug computation must match `BOSS_LOOP.md` exactly. Single function, used consistently. If we ever build other tools that read meta.json, they should import this function (or duplicate it carefully).
- The `agentboss run --bg` call needs a generous timeout. Claude can take 30+ seconds to reach idle on first launch. Pass `--timeout 180` if agentboss supports it.
- Race: between leasing the worktree and spawning agentboss, the worktree path must be captured from `git-worktree open`'s stdout (it prints the path then blocks). The Python wrapper should start `git-worktree open` as a subprocess, read the first line of stdout, then proceed without waiting for it to exit (it's the lease holder — it MUST stay alive for the session to keep its slot).

## Tooling that fits this convention

The `meta.json` + section-dir layout is a small, structured contract. Other tools can read or write it without going through `boss spawn`. Some that we'd plausibly want, in rough order of value:

- **`boss-status`** — one-shot summary: parse BOSS.md, parse `meta.json`, query `agentboss status` for each live session, read each worklog's `status:` frontmatter, print a table:
  ```
  SLUG                              SECTION       AGENTBOSS  WORKLOG    SESSION
  add-user-authentication           open          working    working    boss-a3f
  wire-up-password-reset-email      open          idle       blocked    boss-c14
  refactor-config-loader            closed        —          done       —
  ```
- **`boss-orphans`** — validate `meta.json` against BOSS.md and report mismatches (orphans, missing entries, duplicate slugs). Just the validation pass from BOSS_LOOP.md, exposed as a command. Useful for the human to run after editing headers.
- **`boss-friction-harvest`** — scan all section dirs for `worklog.md`, grep `#friction` tags and `## Trouble report` sections, append new ones to `$MDNOTES_ROOT/boss/friction.md` with a dedup pass. Replaces the manual harvesting step in BOSS_LOOP.md.
- **`boss-shell <slug>`** — read `meta.json`, look up the worktree, drop the human into `cd <worktree> && exec $SHELL`. The "human escape hatch" from the original notes.
- **`boss-attach <slug>`** — wrapper for `agentboss attach $(jq -r .[<slug>].session meta.json)`. Saves typing.
- **`boss-edit <slug>`** — open `$EDITOR` at the section dir (or the worklog specifically). Useful for the human to drop a note into `## Notes from boss` without using Claude.
- **`boss-archive <slug>`** — for closed sections: tar up the section dir + clear it from active disk (still keep the meta.json entry as a pointer). Only worth building once you have many closed sections accumulating.

None of these are needed for v1. They're listed to make the case that **the convention enables them** — once `meta.json` exists as a stable interface, each of these is 50–100 lines of Python that can be written independently of the boss skill itself, by anyone (or any agent) who can read the spec in this file and `BOSS_LOOP.md`.

The key insight: the boss is mostly just **a human-readable convention plus one spawn helper**. Everything else is open to extension.

## Future, explicitly out of scope

- `boss spawn-from-doc` — read the next un-spawned section from BOSS.md and spawn it. Convenient but the boss Claude session can do this in two calls (read BOSS.md, call `boss spawn`).
- `boss info <session>` — print everything we know about a session. Punt until we know what "everything" is.
- Multiple boss docs in flight at once. Punt — one boss assumption is in the spec.
- A daemon that watches BOSS.md and auto-spawns. Way too magical for v1.
