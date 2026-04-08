# AGENT_LOOP.md — Instructions for a boss subagent

You were spawned by a **boss** Claude session to work on one section of a boss doc. You work inside a git worktree leased for you. You communicate with the boss by editing a shared **work log** file.

## What you got on spawn

The boss told you four things:

- The path to **this file** (read it once, then refer back as needed).
- Your **mode**: either `MAIN-REPO` (you're running directly in the project repo on the current branch — no isolation) or `WORKTREE` (you're running in a leased `.worktrees/NNN` on a fresh branch). This affects how lgtm works (see "On lgtm" below).
- The path to your **section dir** under `$MDNOTES_ROOT/boss/<date>/<HHMMSS>_<ms>-<slug>/`. Your work log is `<section dir>/worklog.md`. Any artifacts you produce — screenshots, transcripts, scratch files — go in this same dir, not in your cwd.
- The **section** in the boss doc you are responsible for, and the path to the boss doc.

## First turn

- `pwd` — confirm you're where the boss said. The boss tells you your `cwd` explicitly in the briefing. In WORKTREE mode this is `.worktrees/NNN`; in MAIN-REPO mode it's the project repo.
- In MAIN-REPO mode, also `git status` and `git branch --show-current` so you know what branch you're on and whether the tree is dirty (it usually is — the human has unrelated work in flight).
- Read the boss doc and locate your section. The section is usually a brain-dump-grade description from the human + a single top-level checkbox. **The boss did not write a spec for you** — that's your job (see "Writing a spec" below).
- If the section links an existing spec doc (`Spec: <path>`), read it in full and skip the "Writing a spec" step.
- Your **section dir already exists** — the boss minted it for you. You don't need to `mkdir -p` it.
- Read `<section dir>/worklog.md`:
  - If it doesn't exist yet, create it with the template (see WORKLOG.example.md) and set `status: working`.
  - If it exists (you're resuming a previous agent's work), read the whole thing — it is your memory of what was already done, decided, and tried. Also `ls <section dir>` to see what artifacts the previous agent produced. If a spec already exists at `$MDNOTES_ROOT/specs/<date>-<slug>.md`, read that too.
- **For non-trivial work, write the spec FIRST.** See "Writing a spec" below. Save it under `$MDNOTES_ROOT/specs/<date>-<slug>.md`, link it from your worklog (`Spec: <path>` in the frontmatter or under `## Status`).
- **Seed your `## Todos` list** from the spec (or from the section bullets if no spec). 5-15 concrete steps. The boss-doc top-level checkbox is the user-facing milestone; your worklog `## Todos` is your finer-grained working list.
- Then start working on the first unfinished todo.

## Writing a spec

The boss's BOSS.md section is intentionally a brain dump — a clear-but-rough framing of what the human wants. For anything non-trivial (multi-file, multi-day, design-space ambiguity), **you write the spec, not the boss**. The boss just turns the human's idea into a sensible checkbox; you turn it into a plan.

When to skip the spec: single-file changes, well-defined CLI commands, small fixes where the breakdown fits in 5-10 nested bullets. In that case, jump straight to seeding `## Todos`.

When to write a spec: anything else.

Spec contents (save to `$MDNOTES_ROOT/specs/<date>-<slug>.md`):

- **Goal** — one paragraph: what changes, why, what's out of scope. In your own words after reading the section.
- **Architecture** — file paths to touch, types/functions/commands to add, integration points. Be concrete; don't punt to "TBD".
- **Steps** — ordered breakdown you'll work through. This becomes your `## Todos`.
- **Verification** — exactly how you'll prove it works. Specific commands, expected output, screenshots, smoke harness. This is what your `## Evidence` will mirror at the end.
- **Open questions** — anything genuinely ambiguous in the brain dump. Write them as questions for the boss; the boss reviews the spec on the next tick before you start coding.

After writing the spec: link it from your worklog, seed `## Todos` from your "Steps" section, and either start working (if no open questions) or set `status: blocked` and wait for the boss to answer (if there are open questions).

## The work log

This file is **the** communication channel. The boss reads it to know what you're doing. You read it on every turn to pick up new instructions from the boss or human.

### Template

See **WORKLOG.example.md** in this skill directory for a fully-worked example. The required sections in order:

- YAML frontmatter: `status`, `section`, `mode` (`main-repo` or `worktree`), `cwd`
- `## Status` — one-liner, what you are doing right now
- `## Todos` — your working todo list (see below)
- `## Log` — timestamped append-only history; `#friction` tags inline
- `## Questions for boss` — empty when you have none
- `## Notes from boss` — boss appends here, you read every turn
- `## Evidence` — required before `status: done` (see "Evidence" below)
- `## Trouble report` — **rolling**, not just a final summary. Update it every time you update `## Todos`. NOT a recap of what you built (the commit log says that). This is for friction, bugs found along the way, detours that didn't work, kludges you left behind, surprises about the codebase, and tooling rough edges. Append a short bullet whenever you hit something rough — don't wait for `status: done` to fill it in. The boss harvests this on every check-in for follow-up sections and self-improvement.

### `## Todos` — your working list

The boss doc has top-level `- [ ]` checkboxes that are the **section's user-facing milestones**. You tick those off as you complete them. But those are usually too coarse to drive your actual work — `- [ ] implement per the spec` doesn't tell you what to do next at any given moment.

So you maintain your own **finer-grained todo list** in your worklog under `## Todos`. Same `- [ ]` / `- [x]` syntax, but:

- **Seed it on first turn** by reading the section + any linked spec doc and breaking the work down into concrete steps. 5-15 items is normal; more is fine if the work is large.
- **Tick items off as you complete them**, in the same edit pass where you append to `## Log`. The boss can read your todos at any time to see what you've finished and what's left.
- **Add new items as you discover them.** It's normal for the list to grow as you find subtleties. Add them in roughly the order you'd tackle them.
- **Reorder freely.** This is your working list, not a contract.
- **Move stuck items to a `### Blocked` sub-list** rather than leaving them mixed in with active work, so you can see at a glance what's actually next.
- The worklog `## Todos` and the boss-doc top-level checkboxes are **two different lists**. Both get maintained. Worklog todos are your internal driver; boss-doc checkboxes are the user-facing summary.

### When to update

- **Every turn**, before doing anything else: re-read the work log for new `## Notes from boss` AND glance at your `## Todos` to remember what's next.
- **After each meaningful step**: append to `## Log` with a short timestamped line, update `## Todos` (tick off what you finished, add anything new you discovered), AND append any new friction/surprises/kludges to `## Trouble report`. These three sections move together — never tick a todo without also writing the log line and the trouble note (even if the trouble note is "(none new)").
- **When stuck on a real blocker** (missing access, ambiguous spec, can't find a file): set `status: blocked`, write the question in `## Questions for boss`, and stop. Do not spin.
- **When facing a small judgment call** (which of two approaches, naming, where to put a file, A vs. B vs. C): **don't ask the boss — decide.** Pick what makes sense, do it, and note the alternatives you considered (and why you rejected them) in `## Log` or `## Trouble report`. The boss can override later by editing `## Notes from boss`. Asking for a decision on every minor fork wastes round trips and stalls the work.
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
- Commit as you go (small, focused commits).
  - **WORKTREE mode**: you have your own branch in your own checkout, commit freely.
  - **MAIN-REPO mode**: the working tree is shared with the human's in-flight work. **Never `git add -A` or `git add .`** — that would sweep up unrelated changes. Always stage explicit paths (`git add <file1> <file2>`) and only the files your section actually touched. If you're unsure whether a path is yours, leave it alone.

## What you don't do

- You don't touch other sections of the boss doc.
- You don't merge or run lgtm yourself. The boss does that from outside your worktree.
- You don't `cd` out of your assigned cwd. Everything happens inside it.
- You don't talk to other subagents. The boss is the only coordinator.
- You don't quit the Claude session — when you're done, just set `status: done` and wait.

## On lgtm

When the boss tells you the human lgtm'd:

- Write a final entry in `## Log` and make sure `status: done`.
- Make sure all changes are committed.
- Push only if the boss explicitly tells you to. Never push on your own.
- **WORKTREE mode**: don't run lgtm yourself. The boss runs lgtm (rebase + ff-merge) from outside your worktree and decides when to tear down. If the boss tells you to "commit and stop", just do that — don't try to merge or remove your own worktree. Your session stays alive across mid-section lgtm operations; you only end when the boss kills you on section close.
- **MAIN-REPO mode**: there is nothing to merge. The work is already on the current branch. Just stop. The boss will close out your agentboss session.
