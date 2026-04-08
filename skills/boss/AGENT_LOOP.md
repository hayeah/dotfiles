# AGENT_LOOP.md — Instructions for a boss subagent

You were spawned by a **boss** Claude session to work on one section of a boss doc. You work inside a git worktree leased for you. You communicate with the boss by editing a shared **work log** file.

## What you got on spawn

The boss told you three things:

- The path to **this file** (read it once, then refer back as needed).
- The path to your **section dir** under `$MDNOTES_ROOT/boss/<date>/<HHMMSS.ms>-<slug>/`. Your work log is `<section dir>/worklog.md`. Any artifacts you produce — screenshots, transcripts, scratch files — go in this same dir, not in your worktree.
- The **section** in the boss doc you are responsible for, and the path to the boss doc.

## First turn

- `pwd` — confirm you're in your worktree (something like `.worktrees/001`).
- Read the boss doc and locate your section. Read the section in full, including all bullets.
- Read `<section dir>/worklog.md`:
  - If it doesn't exist yet, create it with the template (see WORKLOG.example.md) and set `status: working`.
  - If it exists (you're resuming a previous agent's work), read the whole thing — it is your memory of what was already done, decided, and tried. Also `ls <section dir>` to see what artifacts the previous agent produced.
- Then start working on the first unfinished todo in your section.

## The work log

This file is **the** communication channel. The boss reads it to know what you're doing. You read it on every turn to pick up new instructions from the boss or human.

### Template

See **WORKLOG.example.md** in this skill directory for a fully-worked example. The required sections in order:

- YAML frontmatter: `status`, `section`, `worktree`, `dir` (your section dir)
- `## Status` — one-liner, what you are doing right now
- `## Log` — timestamped append-only history; `#friction` tags inline
- `## Questions for boss` — empty when you have none
- `## Notes from boss` — boss appends here, you read every turn
- `## Evidence` — required before `status: done` (see "Evidence" below)
- `## Trouble report` — filled in when `status: done`. NOT a recap of what you built (the commit log says that). This is for friction, bugs found along the way, detours that didn't work, kludges you left behind, and surprises about the codebase. The boss harvests this for follow-up sections and self-improvement.

### When to update

- **Every turn**, before doing anything else: re-read the work log for new `## Notes from boss`.
- **After each meaningful step**: append to `## Log` with a short timestamped line.
- **When stuck**: set `status: blocked`, write the question in `## Questions for boss`, and stop. Do not spin.
- **When the section's todos are all done**: do NOT set `status: done` until you have produced evidence (see "Evidence" below). Then set `status: done`, fill in `## Evidence` and `## Trouble report`, and stop. Wait for the boss to review.
- **Friction**: when you hit a tooling rough edge, hack, or "I had to work around X" — append a `#friction` line to `## Log`. The boss harvests these. Don't make a separate file for it.

### Status discipline

Your `status:` field is how the boss knows what to do with you:

- `working` — actively making progress. Boss leaves you alone.
- `blocked` — you need an answer or decision. Boss will get the human or answer in `## Notes from boss`.
- `done` — section complete. Boss will ask the human for lgtm.

If you stop without updating `status:`, the boss will nudge you. Don't make it nudge you.

## Evidence

Imagine a busy human reviewer asking: **"how do I know this actually works?"** "It compiles" and "tests pass" don't answer that if the tests don't exercise the new behavior. Before you set `status: done`, produce the kind of evidence that would convince a skeptical human, and paste it into `## Evidence` in your work log.

What counts:

- **Backend / library**: full test command + tail of passing output. Tests must exercise the new behavior — if you added an endpoint, write a test that hits it; if you added a function, write a test that calls it with realistic input. Cover obvious failure modes too (bad input, missing data).
- **CLI tool**: a transcript of running the new command with realistic input + the actual output.
- **UI / web**: a screenshot of the new UI in a working state. Save it into your section dir (e.g. `<section dir>/01-signup-flow.png`) and link it from `## Evidence` with a relative path. Use the `browser` skill (Chrome DevTools Protocol) or whatever e2e harness the project has. A screenshot of an error state or empty page is not evidence of success.
- **Bug fix**: a reproduction of the bug (before) + the same reproduction showing it fixed (after).
- **E2E flow**: drive the full flow end-to-end via the project's harness — not isolated unit tests with everything mocked out.

The boss will read your `## Evidence` section like a human reviewer and ask for more if it's not convincing. The boss will NOT cd into your worktree and re-run things — but if the evidence you wrote down is thin, vague, or skips an obvious case, it'll come back as a "not convinced yet, need X" note. Save yourself the round trip: produce the convincing artifact the first time.

If your project doesn't have a harness that can produce real e2e evidence (no integration test setup, no way to screenshot the UI, etc.), that's `#friction` worth flagging. Set `status: blocked` and ask the boss what to do — don't silently downgrade to "tests pass, trust me."

## What you do

- Implement the section's todos.
- Update top-level checkboxes in the boss doc as you complete them: `- [ ]` → `- [x]`.
- Maintain your work log per the rules above.
- Commit as you go (small, focused commits) inside your worktree.

## What you don't do

- You don't touch other sections of the boss doc.
- You don't merge or `git-worktree lgtm` until the human says lgtm via the boss.
- You don't `cd` out of your worktree. Everything happens inside it.
- You don't talk to other subagents. The boss is the only coordinator.
- You don't quit the Claude session — when you're done, just set `status: done` and wait.

## On lgtm

When the boss tells you the human lgtm'd:

- Make sure all changes are committed.
- Push if the boss tells you to.
- From inside your worktree, run `git-worktree lgtm`. This rebases, fast-forward merges, deletes the branch, and kills your lease — which will also end your Claude session.
- Before running `lgtm`, write a final entry in `## Log` and set `status: done` if not already.
