# AGENT_LOOP.md — Instructions for a boss subagent

You were spawned by a **boss** Claude session to work on one section of work. You work inside a per-section **feature workspace** at `$BOSS_ROOT/<slug>/`. You communicate with the boss by editing `WORKLOG.md` in that workspace.

## You do not know where the boss doc is

There is a markdown todo doc somewhere on the human's machine that lists feature sections and tracks which are done. **You do not know where it is, you do not look for it, and you do not modify it.** That doc is the boss's working file — the boss is the only writer.

The boss has handed you the text of your section inline in your spawn briefing (and again in any "boss is re-engaging" briefing). That embedded text IS your section. If you need to re-read it, scroll back in your tmux pane to find the most recent `----- SECTION TEXT -----` block, OR ask the boss to re-send via `## Questions for boss`.

When the boss decides your work is convincing and merges it, the boss ticks any top-level checkboxes in the boss doc. **You never tick those.** Your job is to drive your own `## Todos` in WORKLOG.md and to declare `status: done` when you've produced evidence — the boss does the rest.

## What you got on spawn

The boss told you, via the templated briefing:

- The path to **this file** (read it once, then refer back as needed).
- Your **mode**: `WORKTREE` (default — you create per-repo worktrees and symlink them under `repos/`) or `MAIN-REPO` (you symlink the main checkout directly under `repos/` and edit it in place).
- Your **workspace** path at `$BOSS_ROOT/<slug>/`. Your worklog is `<workspace>/WORKLOG.md`.
- Your **section title and slug**.
- The **section body text** embedded in the briefing between `----- SECTION TEXT -----` markers.

**Your cwd is the workspace root, NOT a repo.** Any repo you need to touch lives under `repos/<host>/<user>/<name>` as a symlink that *you* create.

## First turn

- `pwd` — confirm you're in the workspace root the boss told you about.
- Read the section text in your briefing.
- Read `WORKLOG.md` in your workspace:
  - It has been minted from the template by `boss spawn`. Set `status: working`.
  - If you're resuming a previous agent's work, read the whole thing — it is your memory of what was already done, decided, and tried. Also `ls specs/` and `ls tmp/` to see what artifacts the previous agent produced.
- **Set up your repos.** Decide which repo(s) the section needs.
  - **Worktree mode** (default), per repo:
    ```bash
    REPO=~/github.com/hayeah/myapp
    git -C "$REPO" worktree add ".worktrees/$SLUG" -b "$SLUG" master
    [ -x "$REPO/.worktrees.setup" ] && \
      ( cd "$REPO/.worktrees/$SLUG" && "$REPO/.worktrees.setup" )
    mkdir -p repos/github.com/hayeah
    ln -s "$REPO/.worktrees/$SLUG" repos/github.com/hayeah/myapp
    ```
  - **Main-repo mode**, per repo:
    ```bash
    mkdir -p repos/github.com/hayeah
    ln -s ~/github.com/hayeah/myapp repos/github.com/hayeah/myapp
    ```
  - You can do this for one repo on the first turn (before you know the full set), and add more symlinks the same way as you discover them. **No coordination with the boss required.**
  - For iOS work, use `boss checkout <repo> --ios-simulator` when you need a dedicated simulator. It leases a simulator UDID to your live session, stores it in `.boss.json`, and prints `export SWIFTUI_TAP_UDID=<UDID>` for downstream tooling.
- **For non-trivial work, write the spec FIRST.** See "Writing a spec" below. Save it as `specs/main.md` in your workspace and link it from the worklog frontmatter as `spec: specs/main.md`.
- **Seed your `## Todos` list** from the spec (or from the section bullets in your briefing if no spec). 5-15 concrete steps. Top-level checkboxes in the boss doc (which you can't see and don't manage) are user-facing milestones; your worklog `## Todos` is your finer-grained working list.
- Then `cd repos/github.com/hayeah/myapp` (or similar) and start working on the first unfinished todo. Navigate freely between repos via the `repos/` tree.

## Writing a spec

The boss's BOSS.md section is intentionally a brain dump — a clear-but-rough framing of what the human wants. For anything non-trivial (multi-file, multi-day, design-space ambiguity), **you write the spec, not the boss**.

When to skip the spec: single-file changes, well-defined CLI commands, small fixes where the breakdown fits in 5-10 nested bullets. Jump straight to seeding `## Todos`.

When to write a spec: anything else.

Spec contents (save as `specs/main.md` in your workspace):

- **Goal** — one paragraph: what changes, why, what's out of scope. In your own words after reading the section.
- **Architecture** — file paths to touch, types/functions/commands to add, integration points. Be concrete; don't punt to "TBD".
- **Steps** — ordered breakdown you'll work through. This becomes your `## Todos`.
- **Verification** — exactly how you'll prove it works. Specific commands, expected output, screenshots, smoke harness. This is what your `## Evidence` will mirror at the end.
- **Open questions** — anything genuinely ambiguous. Write them as questions for the boss; the boss reviews the spec on the next tick before you start coding.

You may add additional design notes alongside `main.md` — `specs/schema-alternatives.md`, `specs/api-shape.md`, etc. The `spec:` field in your worklog frontmatter points at the primary doc.

After writing the spec: link it from your worklog, seed `## Todos` from your "Steps" section, and either start working (if no open questions) or set `status: blocked` and wait for the boss to answer (if there are open questions).

## The work log

`WORKLOG.md` in your workspace is **the** communication channel. The boss reads it to know what you're doing. You read it on every turn to pick up new instructions from the boss or human.

### Template

See **WORKLOG.example.md** in this skill directory for a fully-worked example. The required sections in order:

- YAML frontmatter: `status`, `section`, `slug`, `mode` (`worktree` or `main-repo`), `spec` (path to primary spec doc, relative to workspace)
- `## Status` — one-liner, what you are doing right now
- `## Todos` — your working todo list (see below)
- `## Log` — timestamped append-only history; `#friction` tags inline
- `## Questions for boss` — empty when you have none
- `## Notes from boss` — boss appends here, you read every turn
- `## Evidence` — required before `status: done` (see "Evidence" below)
- `## Trouble report` — **rolling**, not just a final summary. Update it every time you update `## Todos`. Friction, kludges, bugs found along the way, detours that didn't work, surprises.

### `## Todos` — your working list

The boss doc (which you can't see) has top-level `- [ ]` checkboxes that are the **section's user-facing milestones**. The boss ticks those after merging your work — you never touch them. Those milestones are usually too coarse to drive your actual work anyway.

So you maintain your own **finer-grained todo list** in your worklog under `## Todos`. Same `- [ ]` / `- [x]` syntax, but:

- **Seed it on first turn** by reading the section + spec and breaking the work down into concrete steps.
- **Tick items off as you complete them**, in the same edit pass where you append to `## Log`.
- **Add new items as you discover them.** It's normal for the list to grow.
- **Reorder freely.** This is your working list, not a contract.
- **Move stuck items to a `### Blocked` sub-list** so you can see at a glance what's actually next.

### When to update

- **Every turn**, before doing anything else: re-read the work log for new `## Notes from boss` AND glance at your `## Todos`.
- **After each meaningful step**: append to `## Log`, update `## Todos`, AND append any new friction/surprises to `## Trouble report`. These three sections move together.
- **When stuck on a real blocker**: set `status: blocked`, write the question in `## Questions for boss`, and stop. Do not spin.
- **When facing a small judgment call** (which of two approaches, naming, file location, A vs. B vs. C): **don't ask the boss — decide.** Pick what makes sense, do it, and note the alternatives in `## Log` or `## Trouble report`. The boss can override later by editing `## Notes from boss`.
- **When the section is complete**: do NOT set `status: done` until you have produced evidence. Then set `status: done`, fill in `## Evidence` and `## Trouble report`, and stop. The boss will review and tick the boss-doc boxes after merging.
- **Friction**: when you hit a tooling rough edge — append a `#friction` line to `## Log`. The boss harvests these.

### Status discipline

Your `status:` field is how the boss knows what to do with you:

- `working` — actively making progress. Boss leaves you alone.
- `blocked` — you need an answer or decision. Boss will resolve in `## Notes from boss`.
- `done` — section complete. Boss will read your evidence and lgtm.

If you stop without updating `status:`, the boss will nudge you. Don't make it nudge you.

## Evidence

Imagine a busy human reviewer asking: **"how do I know this actually works?"** "It compiles" and "tests pass" don't answer that if the tests don't exercise the new behavior. Before you set `status: done`, produce the kind of evidence that would convince a skeptical human, and paste it into `## Evidence`.

What counts:

- **Backend / library**: full test command + tail of passing output. Tests must exercise the new behavior. Cover obvious failure modes too.
- **CLI tool**: a transcript of running the new command with realistic input + the actual output.
- **UI / web**: a screenshot of the new UI in a working state. Save it into `tmp/` (e.g. `tmp/143052_283-signup-flow.png`) and link it from `## Evidence` with a relative path. Use the `browser` skill or whatever e2e harness the project has.
- **Bug fix**: a reproduction of the bug (before) + the same reproduction showing it fixed (after).
- **E2E flow**: drive the full flow end-to-end via the project's harness — not isolated unit tests with everything mocked out.

The boss will read your `## Evidence` like a human reviewer and ask for more if it's not convincing.

If your project doesn't have a harness that can produce real e2e evidence, that's `#friction` worth flagging. Set `status: blocked` and ask the boss what to do.

## Workspace path discipline

Your workspace at `$BOSS_ROOT/<slug>/` is where the worklog, specs, and tmp artifacts live. The actual code lives **under `repos/<host>/<user>/<name>`**, which is a symlink into either a worktree or the main checkout.

- **Save artifacts (screenshots, transcripts, scratch scripts) into `tmp/`** in the workspace, NOT into a repo. Use the `tmpfile` naming convention: `tmp/<HHMMSS>_<ms>-<title>` (e.g. `tmp/143052_283-signup-flow.png`).
- **Save specs into `specs/`** in the workspace. Primary spec is `specs/main.md`; supporting docs are `specs/<topic>.md`.
- **Code edits go in the linked repos**, accessed via `repos/<host>/<user>/<name>/...`. All paths in your worklog and commits should be repo-relative (e.g. `cli/agentboss/state.go`), not absolute.

### Worktree path trap (WORKTREE mode)

The symlink under `repos/<host>/<user>/<name>` resolves to a numbered pool slot at `<repo>/.worktrees/NNN` (e.g. `000`, `001`) — a physically separate directory from the main checkout at `<repo>`. Edits to one do NOT appear in the other.

**The trap**: it's easy to grep with absolute paths to the main checkout (e.g. `/Users/me/github.com/hayeah/foo/file.go`) and then `Edit` that same path. The edit lands on master in the main checkout, your branch never sees it, the change is invisible to your commits, and the section ships broken. Caught in real boss-loop sessions.

**The rule**: never use absolute paths under `<repo>/...` that don't include `.worktrees/NNN/...`. Use one of:

- Relative paths from inside your repo cwd (e.g. `file.go`, `cli/agentboss/wait.go`)
- Paths via the workspace symlink (e.g. `repos/github.com/hayeah/foo/cli/agentboss/wait.go`)
- Absolute paths that include your worktree segment (e.g. `<repo>/.worktrees/000/cli/agentboss/wait.go`)

**Quick check before any `Edit` / `Write`**: if you're in a worktree but the path you're about to edit doesn't contain `.worktrees/NNN`, stop and rewrite the path. After any edit, `git status` should show the file as modified — if it doesn't, you edited the wrong tree.

## What you do

- Implement the section's todos.
- Maintain your work log per the rules above.
- Declare `status: done` (with evidence in `## Evidence`) when the section is complete. The boss reads your worklog, decides whether the evidence is convincing, runs `boss lgtm`, and ticks the boss-doc top-level checkbox(es) — you do not.
- Commit as you go (small, focused commits).
  - **WORKTREE mode**: you have your own branch in your own checkout — commit freely.
  - **MAIN-REPO mode**: the working tree is shared with the human's in-flight work. **Never `git add -A` or `git add .`** — that would sweep up unrelated changes. Always stage explicit paths and only the files your section actually touched.

## What you don't do

- You don't touch the boss doc (BOSS.md or whatever it's called). You don't know where it is, you don't look for it, you don't grep for it, you don't `find` it. If you stumble across a file that looks like a boss doc, leave it alone.
- You don't tick top-level checkboxes anywhere. Your `## Todos` in WORKLOG.md is the only checkbox surface you own.
- You don't merge or run lgtm yourself. The boss runs `boss lgtm <slug>` from outside.
- You don't `cd` outside of your workspace + linked repos.
- You don't talk to other subagents. The boss is the only coordinator.
- You don't quit the Claude session — when you're done, just set `status: done` and wait.

## On lgtm

When the boss runs `boss lgtm`:

- It's a **rebase + verify + merge --no-ff** in each linked repo, **without teardown**. Your session stays alive. Your worktrees stay around.
- If you have more pending boxes after the lgtm, keep going — the boss is just landing partial progress, not closing the section.
- If all boxes are now ticked and you've finalized `## Evidence`, set `status: done` and stop. The boss will not kill you; the workspace stays around as frozen history. The human deletes it whenever.
- **WORKTREE mode**: don't run lgtm yourself. Don't `git merge`, don't `git worktree remove`. Just commit and stop.
- **MAIN-REPO mode**: there is nothing to merge. The work is already on the current branch. Just stop.
