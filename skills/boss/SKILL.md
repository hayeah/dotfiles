---
name: boss
description: Coordinate multiple subagent sessions from a single Claude Code session via a markdown todo doc (BOSS.md). Each section gets a per-slug "feature workspace" with worklog + spec + symlinked worktrees. Use when the user wants to "boss-loop", coordinate parallel feature work, or run an outer loop over subagents.
---

# boss

A single Claude Code session (the **boss**) drives multiple subagent sessions through a markdown todo doc. Each top-level section in the doc is a feature; sections get a **feature workspace** under `$BOSS_ROOT/<slug>/` and a subagent. Boss and subagent communicate by editing the workspace's `WORKLOG.md`.

## Files in this skill

- **SKILL.md** (this file) — overview, workspace anatomy, how to find the boss doc
- **BOSS_LOOP.md** — instructions for the boss session (you, when bossing)
- **AGENT_LOOP.md** — instructions injected into each subagent on spawn
- **BOSS.example.md** — example boss doc showing the format
- **WORKLOG.example.md** — example workspace worklog
- **src/boss/** — Python implementation of the `boss` CLI (`boss spawn / ls / lgtm / doctor`)

## When to use this skill

- The user says "let's run the boss loop", "start bossing", "work on BOSS.md", or similar.
- The user points you at a specific markdown todo doc and wants you to coordinate work on it.
- The user wants you to spawn and supervise subagents instead of doing the work yourself.

## The two layers

- **`agentboss`** (Go, separate repo) is the *process layer*: tmux + claude/codex supervisor, state files, event bus, `agentboss run/ls/state/wait/send/kill`. Doesn't know about workspaces, sections, or BOSS.md.
- **`boss`** (Python, this skill, `uv tool install -e .`) is the *workflow layer*: reads BOSS.md, manages workspaces, calls `agentboss` to spawn/inspect/wait, coordinates lgtm. Four verbs: `spawn`, `ls`, `lgtm`, `doctor`.

The boss session (you, the human-facing Claude) calls `boss <verb>` for things the CLI mechanizes, and runs raw shell (`agentboss state/output/send`, `cat`, `git`) for everything else.

## Finding the boss doc

In order:

- If the user named a file, use that.
- Otherwise, look for `BOSS.md` in the current working directory.
- If neither exists, ask the user where the boss doc is or whether to create one from `BOSS.example.md`.

There is only one boss at a time. The boss doc needs no frontmatter — just top-level sections.

## Workspace anatomy

`$BOSS_ROOT` defaults to `~/Dropbox/boss/`. Override with `$BOSS_ROOT` env var.

```
$BOSS_ROOT/                          # default: ~/Dropbox/boss/
  friction.md                        # cross-section friction harvest (boss appends)
  add-user-authentication/           # workspace = slug, no timestamp
    WORKLOG.md                       # the durable channel (status, log, todos, evidence, trouble report)
    specs/                           # design docs the agent writes on first turn
      main.md                        # primary spec (linked from WORKLOG.md frontmatter `spec:`)
      schema-alternatives.md         # ad-hoc supporting notes (optional)
    repos/                           # symlinks ONLY (excluded from Dropbox sync)
      github.com/hayeah/myapp -> ~/github.com/hayeah/myapp/.worktrees/000
      github.com/hayeah/myapp-shared -> ~/github.com/hayeah/myapp-shared/.worktrees/001
    tmp/                             # inspectable outputs (screenshots, transcripts, scratch scripts)
      143052_283-signup-flow.png     # use the tmpfile naming convention: HHMMSS_<ms>-<title>
      143205_117-schema-dump.sql
  fix-oauth-redirect/
    WORKLOG.md
    repos/github.com/hayeah/myapp -> ~/github.com/hayeah/myapp   # main-repo mode: link straight at the main checkout
```

Key properties:

- **The slug is the join key.** No timestamp prefix, no internal id, no `meta.json`. Workspace exists ↔ section is open.
- **`specs/` is a directory.** The agent writes `specs/main.md` on first turn for non-trivial sections, may add supporting docs (`specs/schema-alternatives.md`, etc.). WORKLOG.md frontmatter `spec:` field points at the primary one.
- **`tmp/` holds inspectable outputs** — screenshots, transcripts, repro scripts. Use the `tmpfile` naming convention: `<HHMMSS>_<ms>-<title>`. The underscore between seconds and ms survives claude's project-id encoding (which rewrites `/` and `.` to `-`).
- **`repos/` contains only symbolic links.** Worktrees live in numbered pool slots at `~/github.com/<user>/<repo>/.worktrees/NNN/` (e.g. `000`, `001`). The workspace just has links into them.
- **Why symlinks, not worktrees-in-place**: Dropbox would sync the worktree contents, which is wasteful and confusing. Symlinks are tiny and Dropbox follows them as files.
- **Dropbox-sync exclusion**: add `repos/` to the Dropbox ignore list (or use the `.nosync` extension on macOS) so Dropbox doesn't follow the symlinks.
- **No section-state ledger.** Section state is derived: `boss ls` parses BOSS.md, checks `$BOSS_ROOT/<slug>/`, and asks `agentboss` if a session exists with that cwd.

## Modes

- **Worktree mode (default).** The agent runs `boss checkout <repo>` which leases a numbered pool slot at `<repo>/.worktrees/NNN` via `agentboss lease`. The pool asks `agentboss lease-check` for slot ownership, reuses the current workspace's slot when possible, otherwise finds a free slot or grows a new one, resets tracked files to master (build artifacts survive), creates a branch named `<slug>`, and symlinks the slot under `repos/<host>/<user>/<name>`. Multi-repo sections add more symlinks the same way as the agent discovers what it needs.
- **Main-repo mode** (rare; for serialized work where worktrees would be overhead). The agent symlinks the main checkout directly into `repos/`. Same restrictions as before: never `git add -A`, only stage explicit paths, the working tree is shared with the human's in-flight work.
- **iOS simulator option.** `boss checkout <repo> --ios-simulator` also leases a dedicated simulator UDID to the live session, boots it, stores the UDID in `.boss.json`, and prints the corresponding `SWIFTUI_TAP_UDID` export.

The boss tells the agent which mode in the spawn briefing. If the section text says "edit in place" / "no worktree", main-repo mode. Otherwise worktree mode. `boss spawn --mode <mode>` selects.

## Doneness — no `[x]` prefix, no nested checkboxes

A section is "done" when every **top-level** `- [ ]` checkbox in its body is ticked. The section header never gets a `[x]` prefix. The boss tooling derives doneness from the body, not the header.

The grammar boss recognizes inside a section body:

- **Top-level checkbox lines**: `- [ ]` or `- [x]` at column zero. Each is a coarse todo the agent ticks when its chunk is done.
- **Nested plain bullets** under a checkbox: instructional breakdown / context for the box above. These MUST be plain `-` bullets (no `[ ]`).
- **Prose paragraphs**: framing context for the section. Ignored by the doneness check.

Example:

```markdown
## Add user authentication

Spec: $BOSS_ROOT/add-user-authentication/specs/main.md

- [ ] design the schema and write the spec
  - read the existing user table
  - prefer UUIDs over auto-increment
- [ ] implement and verify
  - the spec covers schema + endpoint + tests + evidence requirements
  - dogfood with the signup flow
```

`has_pending(section_body)` matches only `^- \[([ x])\]` (zero leading whitespace) — nested checkboxes are silently ignored. `boss doctor` warns when it finds them so the human can fix.

Why the restriction:

- **Predictable doneness.** "All top-level boxes ticked = done" is one rule, not a tree-walk.
- **The agent's WORKLOG.md `## Todos` is where fine-grained step tracking lives.** The boss-doc is the human-facing summary; the worklog is the agent's working list.

Reopening a section = unticking a top-level box (or adding a new one). The human can do this any time without coordinating with the boss; `boss ls` shows it pending again on the next call.

There is no `boss close` verb. The terminal action is `boss lgtm`. The workspace dir stays around as frozen history until the human deletes it.

## Slug rules

The slug function maps a section header to a stable key:

- `## Add user authentication` → `add-user-authentication`
- `## Refactor config loader` → `refactor-config-loader`
- `## Fix OAuth redirect bug!` → `fix-oauth-redirect-bug`

Steps: lowercase, replace runs of non-alphanumerics with `-`, strip leading/trailing `-`. Section headers must be unique by slug within a boss doc (`boss ls` and `boss doctor` reject duplicates).

## CLI surface

Five verbs. See BOSS_LOOP.md for the loop and the shell recipes that fill the gaps.

```
boss add                       # append a new section to BOSS.md (reads from stdin)
  --boss-doc <path>            # default: ./BOSS.md
  --date YYYY-MM-DD            # date group header (default: today)

boss spawn <section>           # set up the workspace and spawn an agent in it
  --mode worktree|main-repo    # default: worktree
  --boss-doc <path>            # default: ./BOSS.md

boss ls                        # wide read: BOSS.md ↔ workspace ↔ agentboss join
  --json                       # machine-readable for the boss session

boss lgtm <section>            # rebase + verify + merge --no-ff each linked repo, with gating

boss doctor                    # report inconsistencies the happy-path verbs ignore
```

What the CLI does NOT do (use shell instead):

| Use case        | Shell recipe                                                                          |
|-----------------|---------------------------------------------------------------------------------------|
| `check`         | `cat $BOSS_ROOT/<slug>/WORKLOG.md && agentboss state <key> && agentboss output <key>` |
| `send`          | edit `$BOSS_ROOT/<slug>/WORKLOG.md` `## Notes from boss`, then `agentboss send <key> "re-read your worklog and continue"` |
| `wait`          | `agentboss wait <key> --timeout 600 &`                                                |
| `harvest`       | `cat $BOSS_ROOT/<slug>/WORKLOG.md` (the `## Trouble report` section), append by hand to `$BOSS_ROOT/friction.md` |
| `recover`       | manual `git worktree prune` per repo + `boss ls` to see what reconciled               |

If any of these starts feeling repetitive in real use, promote it to a verb.

## Safety properties

The Python implementation enforces:

- **`boss spawn` refuses if a live session already has cwd = the workspace.** Duplicate-spawn guard.
- **`boss spawn` constructs the briefing from a template**, not caller-supplied prose.
- **`boss ls` and `boss lgtm` reject duplicate slugs** in BOSS.md.
- **`boss lgtm` pre-flight refuses on dirty-file overlap** between the agent's branch and the main checkout, naming the overlapping files and suggesting `git stash --include-untracked`. Does NOT auto-stash.
- **`boss lgtm` gates teardown on merge success** (today: lgtm doesn't tear down — but the merge gate is still critical when bumping master).
- **The agentboss binary is pinned at startup.** boss validates that `agentboss` on PATH is a gobin shim pointing at the canonical `~/github.com/hayeah/agentboss/cli/agentboss`, then snapshots `~/.gobin/bins/agentboss` to a process-private tmp file for the lifetime of the session. An in-flight subagent rebuilding agentboss can't repoint or overwrite our binary mid-loop.

## What the boss does, what the subagent does

- **Boss**: reads the boss doc, decides what to spawn, talks to subagents through their workspaces, harvests friction, lgtm's. Does NOT write feature code itself.
- **Subagent**: works in its workspace at `$BOSS_ROOT/<slug>/`, sets up its own worktree symlinks under `repos/`, edits `WORKLOG.md` every turn, implements the section.

For the full loop, see **BOSS_LOOP.md**. For the subagent contract, see **AGENT_LOOP.md**.
