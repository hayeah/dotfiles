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
    143052_283-add-user-authentication/
      worklog.md                  # the communication channel
      01-signup-flow.png          # screenshots, transcripts, generated output, anything
      schema.sql
    091200_450-fix-oauth-bug/
      worklog.md
      repro.sh
```

Each section gets its own timestamped directory under today's date — same shape as the `tmpfile` / `/mdnote` convention. The directory IS the section: `worklog.md` is the communication file, and everything else (screenshots, test output, scratch files) goes in the same dir.

The path `<date>/<HHMMSS>_<ms>-<slug>` is the section's section dir. `<slug>` is a kebab-case slug derived from the section header (strip `## `, strip `[x]` / `[ ]`, lowercase, non-alphanumerics → `-`). Generate the timestamp with the `tmpfile` helper or the python one-liner shown below. The underscore between seconds and ms is deliberate — claude's project-id encoder rewrites `/` and `.` to `-`, so a literal `.` would muddle the encoded path.

`meta.json` is the **note-keeping ledger**. It's deliberately minimal — only what isn't derivable from the slug + agentboss. Flat object keyed by section slug:

```json
{
  "add-user-authentication": {
    "header": "Add user authentication",
    "worklog": "2026-04-08/143052_283-add-user-authentication",
    "session": "boss-a3f"
  }
}
```

Three fields:

- `header` — original section header text (for human readability when reading the JSON).
- `worklog` — path to the section dir (containing `worklog.md` and any artifacts), relative to `$MDNOTES_ROOT/boss/`.
- `session` — the agentboss-generated key (e.g. `boss-a3f`).

Everything else is derivable:

- **Worktree path** → `<repo>/.worktrees/<slug>` (the slug IS the dir name; the slug IS the branch name).
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

Subagents run as Claude Code sessions inside tmux windows managed by [agentboss](https://github.com/hayeah/agentboss). **Worktree mode is the default** — every section gets its own per-repo worktree at `<repo>/.worktrees/<slug>` on a branch named `<slug>`. Main-repo mode is the rare opt-out (when the section text says "edit in place" / "no worktree"). See BOSS_LOOP.md "Worktree lifecycle" for the full lifecycle rules.

### Steps

Mint the worklog dir. The relative form (`<date>/<prefix>-<slug>`) is what gets recorded in `meta.json` as the section's `worklog` field.

```bash
DATE=$(date +%Y-%m-%d)
PREFIX=$(python3 -c 'import time;print(time.strftime("%H%M%S")+f"_{int((time.time()%1)*1000):03d}")')
SLUG=add-user-authentication
REPO=~/github.com/hayeah/myproject
SECTION_DIR_REL="$DATE/$PREFIX-$SLUG"
SECTION_DIR="$MDNOTES_ROOT/boss/$SECTION_DIR_REL"
mkdir -p "$SECTION_DIR"
```

(Note: BSD `date` on macOS doesn't support `%N` for sub-second precision, so use the python one-liner above for portability. The `_` separator between `HHMMSS` and `ms` is intentional — see the path-encoding caveat at the top of this section.)

Create the worktree (worktree mode default). Refuse if it already exists — that's an orphan from a prior aborted run.

```bash
# Worktree mode (default)
if [ -e "$REPO/.worktrees/$SLUG" ]; then
  echo "error: orphan worktree at $REPO/.worktrees/$SLUG — surface to human, do not auto-clean"
  exit 1
fi

git -C "$REPO" worktree add ".worktrees/$SLUG" -b "$SLUG" master

# Run the project's setup hook if present (optional executable)
if [ -x "$REPO/.worktrees.setup" ]; then
  ( cd "$REPO/.worktrees/$SLUG" && "$REPO/.worktrees.setup" )
fi

AGENT_CWD="$REPO/.worktrees/$SLUG"
```

For multi-repo sections, repeat the `worktree add` + setup hook in each repo (same slug everywhere). The agent's `--cwd` is the primary repo's worktree; other repos are listed in the briefing for the agent to navigate to.

Main-repo mode (rare opt-out — only when the section says so):

```bash
# Refuse if another main-repo session is already live in this repo (clobber risk)
AGENT_CWD="$REPO"
```

Spawn the Claude session. **Do not pass `--key`** — let agentboss auto-generate one. **Do not pass `--bg`** (removed; `agentboss run` is the spawner now).

```bash
SPAWN_JSON=$(agentboss run \
  --detector claude \
  --cwd "$AGENT_CWD" \
  -- claude --dangerously-skip-permissions)

SESSION_KEY=$(echo "$SPAWN_JSON" | jq -r .key)
```

Write the section's entry into `$MDNOTES_ROOT/boss/meta.json` (read-modify-write, keyed by slug):

```json
{
  "add-user-authentication": {
    "header": "Add user authentication",
    "worklog": "2026-04-08/143052_283-add-user-authentication",
    "session": "boss-a3f"
  }
}
```

Send the initial briefing. Tell the subagent which mode it's in and where things are:

```bash
agentboss send "$SESSION_KEY" "Read ~/github.com/hayeah/dotfiles/skills/boss/AGENT_LOOP.md. You are running in WORKTREE mode at $AGENT_CWD on branch $SLUG. Your section dir is $SECTION_DIR. Your work log is at $SECTION_DIR/worklog.md. Your section in the boss doc is '<section header>' at <boss doc path>. Create worklog.md if it doesn't exist, then begin."
```

Then arm the wait loop: `agentboss wait $SESSION_KEY --timeout 600 &` so the boss is notified the moment the agent goes idle (or the 10-min timeout fires).

**Long briefings:** if the briefing is multi-paragraph, `agentboss send` may paste the message into the input buffer without submitting. After a long send, follow up with `agentboss send <key> "begin"` to flush.

### Talking to a running subagent

Look up the section in `meta.json` by slug to get its `session` and `worklog` fields. Then:

- **Inspect state**: `agentboss <session> status -q` — returns `idle` / `working` / `waiting` / `unknown`.
- **Read pane**: `agentboss output <session> -n 80` — last 80 lines of terminal.
- **Read work log**: `cat $MDNOTES_ROOT/boss/<worklog>/worklog.md` — the durable channel.
- **List artifacts**: `ls $MDNOTES_ROOT/boss/<worklog>/` — see screenshots, transcripts, etc.
- **Find the worktree**: it's `<repo>/.worktrees/<slug>`. The branch is also `<slug>`. No lookup needed.
- **Send a nudge**: `agentboss send <session> "<message>"` — typically just "re-read your worklog and continue".
- **Attach interactively**: `agentboss attach <session>` — for the human to take over.

### Closing a section

The boss decides lgtm itself (the human is not in the loop — see BOSS_LOOP.md). When evidence is convincing:

```bash
# 1. lgtm: rebase, verify build, merge with --no-ff so the merge boundary is visible
git -C "$REPO/.worktrees/$SLUG" rebase master
( cd "$REPO/.worktrees/$SLUG" && go build ./... && go test ./... )   # post-rebase verification
git -C "$REPO" merge --no-ff "$SLUG" -m "Merge branch '$SLUG'"

# 2. VERIFY merge actually landed before any teardown — never chain past a failure
git -C "$REPO" log --oneline -1   # should show the merge commit

# 3. Prefix [x] in BOSS.md (triggers tear-down)
# (edit the section header)

# 4. Tear down — only after merge confirmed
agentboss kill "$SESSION_KEY"
git -C "$REPO" worktree remove ".worktrees/$SLUG"
git -C "$REPO" branch -D "$SLUG"     # -D not -d: with --no-ff plain -d may refuse
# For multi-repo sections, repeat worktree remove + branch -D in each repo

# 5. Clear meta.json[<slug>].session to null (keep header + worklog for history)
```

**Recovery from a botched teardown:** if you delete a branch before confirming the merge, the commits live for ~2 weeks in the object store. `git show <sha>` confirms they're there; `git branch <name> <sha>` recreates the ref.

Leave the worklog dir under `$MDNOTES_ROOT/boss/<worklog>/` in place — it's the section's frozen history.

## What the boss does, what the subagent does

- **Boss**: reads the boss doc, decides what to spawn, talks to subagents through their work logs, harvests friction, asks the human for lgtm. Does NOT write feature code itself.
- **Subagent**: works in its worktree, edits its work log every turn (status + log + friction), implements the section.

For the full loop, see **BOSS_LOOP.md**. For the subagent contract, see **AGENT_LOOP.md**.
