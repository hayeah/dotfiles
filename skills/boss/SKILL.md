---
name: boss
description: Coordinate multiple subagent sessions from a single Claude Code session via a markdown todo doc (BOSS.md). Spawns subagents in tmux + git worktrees through agentboss, communicates with them via shared work logs in Dropbox. Use when the user wants to "boss-loop", coordinate parallel feature work, or run an outer loop over subagents.
---

# boss

A single Claude Code session (the **boss**) drives multiple subagent sessions through a flexible markdown todo doc. Each top-level section in the doc is a feature; sections get a worktree and a subagent. Boss and subagent communicate by editing a shared **work log** file.

This is an MVP. Expect rough edges. When you hit them, append a note to the friction section of the relevant work log so the human can review.

## Files in this skill

- **SKILL.md** (this file) — overview, how to find the boss doc, how to spawn agents
- **BOSS_LOOP.md** — instructions for the boss session (you, when bossing)
- **AGENT_LOOP.md** — instructions injected into each subagent on spawn
- **BOSS.example.md** — example boss doc showing the format
- **WORKLOG.example.md** — example subagent work log showing the required sections
- **CLI.md** — design notes for the eventual `boss spawn` command (not yet implemented; until then, the spawn dance is inlined in BOSS_LOOP.md)

## When to use this skill

- The user says "let's run the boss loop", "start bossing", "work on BOSS.md", or similar.
- The user points you at a specific markdown todo doc and wants you to coordinate work on it.
- The user wants you to spawn and supervise subagents instead of doing the work yourself.

## Finding the boss doc

In order:

- If the user named a file, use that.
- Otherwise, look for `BOSS.md` in the current working directory.
- If neither exists, ask the user where the boss doc is or whether to create one from `BOSS.example.md`.

There is only one boss at a time. The boss doc needs no frontmatter — just top-level sections.

## Where logs live

All per-section artifacts and the friction log live under Dropbox at `$MDNOTES_ROOT/boss/`:

```
$MDNOTES_ROOT/boss/
  meta.json                       # per-section state, keyed by section slug
  friction.md                     # rolling, cross-section harvest (boss appends)
  2026-04-08/
    143052.283-add-user-authentication/
      worklog.md                  # the communication channel
      01-signup-flow.png          # screenshots, transcripts, generated output, anything
      schema.sql
    091200.450-fix-oauth-bug/
      worklog.md
      repro.sh
```

Each section gets its own timestamped directory under today's date — same shape as the `tmpfile` / `/mdnote` convention. The directory IS the section: `worklog.md` is the communication file, and everything else (screenshots, test output, scratch files) goes in the same dir.

The path `<date>/<HHMMSS.ms>-<slug>` is the section's section dir. `<slug>` is a kebab-case slug derived from the section header (strip `## `, strip `[x]` / `[ ]`, lowercase, non-alphanumerics → `-`). Generate the timestamp with the `tmpfile` helper or inline (`date +%Y-%m-%d` and `date +%H%M%S.%3N`).

`meta.json` is the **note-keeping ledger**. It's deliberately minimal — only what agentboss and git-worktree don't already know. Flat object keyed by section slug:

```json
{
  "add-user-authentication": {
    "header": "Add user authentication",
    "worklog": "2026-04-08/143052.283-add-user-authentication",
    "session": "boss-a3f"
  }
}
```

Three fields:

- `header` — original section header text (for human readability when reading the JSON).
- `worklog` — path to the section dir (containing `worklog.md` and any artifacts), relative to `$MDNOTES_ROOT/boss/`.
- `session` — the agentboss-generated key (e.g. `boss-a3f`).

Everything else is derivable:

- **Worktree** → `git-worktree list --json` (find the entry whose `branch` matches the slug).
- **Tmux target** → `__agent:<session>` by agentboss convention.
- **Worklog file** → `$MDNOTES_ROOT/boss/<worklog>/worklog.md`.
- **Artifacts** → `ls $MDNOTES_ROOT/boss/<worklog>/`.
- **Spawned-at, cwd, command** → `agentboss` knows.

The boss doc itself stays clean — just headers and `[ ]` todos. All persistent state lives in `meta.json`. The slug is the join key between the boss doc, the worklog dir, the worktree (by branch name), and the agentboss session.

### Slug rules

The slug function maps a section header to a stable key:

- `## Add user authentication` → `add-user-authentication`
- `## [x] Refactor config loader` → `refactor-config-loader`
- `## Fix OAuth redirect bug!` → `fix-oauth-redirect-bug`

Steps: strip leading `## `, strip leading `[x]` / `[ ]`, trim, lowercase, replace runs of non-alphanumerics with `-`, strip leading/trailing `-`.

### Stability requirements

- **Section headers must be unique** within a boss doc (after slugifying). Duplicate slugs are a hard error — boss refuses to operate.
- **Renaming a header detaches its metadata.** If you change a header, the `meta.json` entry under the old slug becomes orphaned. Boss surfaces orphans on each tick and refuses to operate until the human resolves them (manually edit `meta.json` to rename the key, or delete the orphan).
- **Closed state lives in the header**, not in `meta.json`. The `[x]` prefix on a header is the source of truth; nothing in JSON duplicates it.

Create the section dir on spawn: `mkdir -p "$MDNOTES_ROOT/boss/<date>/<prefix>-<slug>"`.

## Spawning a subagent

Subagents run as Claude Code sessions inside tmux windows managed by [agentboss](https://github.com/hayeah/agentboss). By default they run **directly in the project repo** on the current branch. If the section text indicates the work should be isolated (e.g. "use a worktree", "in a worktree", "branch off origin/master"), lease a git worktree via the `git-worktree` skill and run the agent there instead. See BOSS_LOOP.md "Worktree mode vs. main-repo mode".

### Steps

Mint the worklog dir and remember its path. The relative form (`<date>/<prefix>-<slug>`) is what gets recorded in `meta.json` as the section's `worklog` field.

```bash
DATE=$(date +%Y-%m-%d)
PREFIX=$(date +%H%M%S.%3N)
SLUG=add-user-authentication
SECTION_DIR_REL="$DATE/$PREFIX-$SLUG"
SECTION_DIR="$MDNOTES_ROOT/boss/$SECTION_DIR_REL"
mkdir -p "$SECTION_DIR"
```

Decide the agent's cwd. **Default**: the project repo. **If the section asked for a worktree**: lease one (background — `open` blocks):

```bash
# Default — main-repo mode
AGENT_CWD=<project repo>

# OR — worktree mode (only if the section asked for it)
cd <project repo>
git-worktree open "$SLUG" --base origin/master &
# capture the printed worktree path, e.g. .worktrees/001
AGENT_CWD=<worktree path>
```

In main-repo mode, **first check that no other section is already running in main-repo mode**. Two subagents editing the same files at once will clobber each other. If one is already live, refuse and tell the human.

Spawn the Claude session at `$AGENT_CWD`. **Do not pass `--key`** — let agentboss auto-generate one. Capture the JSON it prints:

```bash
SPAWN_JSON=$(agentboss run --bg \
  --detector claude \
  --cwd "$AGENT_CWD" \
  -- claude --dangerously-skip-permissions)

# Extract the auto-generated key (looks like "boss-a3f")
SESSION_KEY=$(echo "$SPAWN_JSON" | jq -r .key)
```

`--bg` waits for Claude to reach idle and prints a JSON descriptor with `key`, `short_id`, `tmux_target`, etc. Then write the section's entry into `$MDNOTES_ROOT/boss/meta.json` (read-modify-write, keyed by slug):

```json
{
  "add-user-authentication": {
    "header": "Add user authentication",
    "worklog": "2026-04-08/143052.283-add-user-authentication",
    "session": "boss-a3f"
  }
}
```

Send the initial briefing. Tell the subagent which mode it's in so it knows whether to expect a worktree and how to handle lgtm later:

```bash
# In main-repo mode — say so explicitly
agentboss send "$SESSION_KEY" "Read ~/github.com/hayeah/dotfiles/skills/boss/AGENT_LOOP.md. You are running in MAIN-REPO mode (no worktree). Your section dir is $SECTION_DIR. Your work log is at \$SECTION_DIR/worklog.md. Your section in the boss doc is '<section header>' at <boss doc path>. Create worklog.md if it doesn't exist, then begin."

# In worktree mode
agentboss send "$SESSION_KEY" "Read ~/github.com/hayeah/dotfiles/skills/boss/AGENT_LOOP.md. You are running in WORKTREE mode at $AGENT_CWD. Your section dir is $SECTION_DIR. Your work log is at \$SECTION_DIR/worklog.md. Your section in the boss doc is '<section header>' at <boss doc path>. Create worklog.md if it doesn't exist, then begin."
```

### Talking to a running subagent

Look up the section in `meta.json` by slug to get its `session` and `worklog` fields. Then:

- **Inspect state**: `agentboss status <session> -q` — returns `idle` / `working` / `waiting` / `unknown`.
- **Read pane**: `agentboss output <session> -n 80` — last 80 lines of terminal.
- **Read work log**: `cat $MDNOTES_ROOT/boss/<worklog>/worklog.md` — the durable channel.
- **List artifacts**: `ls $MDNOTES_ROOT/boss/<worklog>/` — see screenshots, transcripts, etc.
- **Find the worktree**: `git-worktree list --json | jq '.[] | select(.branch=="<slug>")'`. The branch name is the slug by convention.
- **Send a nudge**: `agentboss send <session> "<message>"` — typically just "re-read your worklog and continue".
- **Attach interactively**: `agentboss attach <session>` — for the human to take over.

### Closing a section

When the human says lgtm on a section:

- Mark the section header in the boss doc as done by prefixing it with `[x]` (e.g. `## [x] Add user authentication`).
- **Worktree mode**: tell the subagent to commit, then run `git-worktree lgtm` from inside the worktree. `lgtm` rebases, fast-forward merges, deletes the branch, and kills the lease holder (which ends the Claude session).
- **Main-repo mode**: tell the subagent to commit on the current branch and stop. There's nothing to merge — the work is already on the branch. The subagent quits its session after the final log entry; the boss kills the agentboss window via `agentboss` if the subagent doesn't.
- Leave the worklog dir under `$MDNOTES_ROOT/boss/<worklog>/` in place — it's the section's frozen history.
- Clear the `session` field in the meta.json entry to `null` (the agentboss key is gone). Keep `header` and `worklog` so the entry still points at the frozen history.

## What the boss does, what the subagent does

- **Boss**: reads the boss doc, decides what to spawn, talks to subagents through their work logs, harvests friction, asks the human for lgtm. Does NOT write feature code itself.
- **Subagent**: works in its worktree, edits its work log every turn (status + log + friction), implements the section.

For the full loop, see **BOSS_LOOP.md**. For the subagent contract, see **AGENT_LOOP.md**.
