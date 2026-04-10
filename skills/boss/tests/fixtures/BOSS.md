# Dotfiles BOSS

Boss doc for the boss-skill smoke test. Iterate freely.

## Smoke test the boss skill

Just a hello-world section to confirm the spawn pipeline works end-to-end.

- [x] confirm you can read this section from BOSS.md
- [x] write your initial worklog.md with status: working
- [x] add a one-line note to `## Log` saying you're alive
- [x] set status: done with a trivial `## Evidence` block (e.g. paste the output of `pwd` and `git status`)

No code changes. Just exercise the worklog + evidence flow.

## Polish the boss skill from real usage

After the smoke test, write down what was rough about the spawn → run → close loop. Don't fix anything yet — just collect notes in `## Trouble report` format and we'll triage together.

- [x] note any spawn/briefing pain points
- [x] note anything confusing about the AGENT_LOOP.md instructions
- [x] note any ergonomic gaps in the boss CLI

## Add per-session supervisor process to agentboss

Upstream work on the agentboss repo (use a worktree off origin/master in `~/github.com/hayeah/agentboss`). The boss skill's contract with agentboss does **not** change.

Spec: `~/Dropbox/notes/2026-04-08/agentboss-supervisor-spec_claude.md` — read this first, follow it.

- [x] implement per the spec
- [x] verify per the spec's "Verification" section
- [x] add codex support via log tailing (mirror the claude transcript watcher — find codex's session log, tail it, drive state transitions from log entries only, no pane scraping)

## Add `agentboss shell <HASH>` command

Spawn an interactive shell in the cwd of the given tmux session. Useful for jumping into a subagent's worktree without typing the path.

- [x] add `agentboss shell <HASH>` that execs `$SHELL` at the session's recorded cwd
  - resolve HASH via the agentboss store (key or short-id)
  - fall back to `/bin/bash` if `$SHELL` is unset
  - register in `main.go`, add help text, smoke test

## Switch `agentboss ls` to read state.json, retire DetectorRunner + legacy detectors

`agentboss ls` currently runs the live pane detector on every call regardless of what the supervisor's state.json says. A broken supervisor stuck at "alive" appears "idle" in `ls`, hiding bugs — you have to read state.json directly (or `subscribe`) to see what state the supervisor actually published. Fix `ls` to read state.json. Once that lands, audit DetectorRunner — it's still in the wire graph for `ls` and `ExpectEngine`; if `ls` is the only thing keeping it, remove it. Also delete the legacy Python detectors in `~/.agentboss/detectors/` — they're dead code from the supervisor's perspective (post-cc6 ClaudeWatcher/CodexWatcher rewrite).

- [x] implement and verify
  - `agentboss ls` reads state.json (or briefly subscribes to the SSE socket) instead of running the pane detector live
  - audit DetectorRunner usage; if `ls` is the only consumer left after this change, remove the type from the wire graph; otherwise leave it with a comment about who still needs it
  - delete `~/.agentboss/detectors/` Python files and any installer code that copies them in
  - regression: kill -9 a child, run `ls`, confirm it shows the post-death state correctly without re-running a detector
  - coordinate with the parallel "Fix `agentboss wait`" section — both touch the same SSE/state.json area

## Fix `agentboss wait` to subscribe to state transitions

`agentboss wait HASH --timeout N` returns immediately when called on a freshly-spawned agent because state.json contains `idle` (the post-spawn snapshot — claude is sitting at the prompt with no input yet). It doesn't distinguish "idle waiting for first input" from "idle finished a turn." Boss workflow needs the second meaning. Reproduced today: spawned 3 agents, immediately armed `wait` on each, all 3 returned in <1s even though the agents were genuinely working. Same root cause as the `ls` bug: reads cached state instead of subscribing to state transitions on the SSE bus.

- [x] implement and verify
  - `agentboss wait` subscribes to the supervisor's SSE event bus and reacts to state *transition* events, not the cached state.json snapshot
  - add a `--from <state>` flag (e.g. `--from working`) so callers can wait for "transition from X to idle" specifically. Default behavior should still be "wait for next idle event", interpreted as "block until you observe a state transition that ends in idle" — never return on the bus's initial snapshot
  - regression: spawn a fresh agent, immediately `agentboss wait <key> --timeout 60`, send a `Bash(sleep 30)` task, confirm wait blocks ~30s (not <1s)
  - regression: agent already mid-task → `agentboss wait <key>` returns when the task completes
  - this section touches `cli/agentboss/wait.go` + the SSE event consumer; coordinate with the parallel "Switch `agentboss ls`" section since both touch the same SSE/state.json area

## Codex code review + cleanup pass on agentboss

After several parallel feature branches landed today (claudewatcher, codexwatcher, tailFile helper, ls→state.json refactor, wait→SSE), the agentboss codebase has accumulated stale code, leftover comments, and likely some smells worth cleaning up. Use codex CLI as a second pair of eyes — its review style differs from claude's and tends to catch things claude wrote and missed.

- [x] implement and verify
  - run a codex review pass over agentboss: `cd ~/github.com/hayeah/agentboss && codex exec "review the codebase for stale code, dead branches, leftover comments, and obvious cleanup opportunities"` (or whatever the right invocation is — check `codex --help`)
  - save the raw codex output as `<section dir>/codex-review.md`
  - triage findings: keep stale/dead code removals + clear smells; drop nitpicks and out-of-scope rewrites
  - apply the kept fixes — small focused commits, one per logical cleanup
  - run `go build ./... && go vet ./... && go test ./...` after each commit cluster
  - the agent doing this is claude (not codex itself) — codex provides the review, claude applies the fixes
  - skip anything that overlaps with the parallel "Show state age" section (5d2 is touching state events / classifyEntry)
  - **out of scope**: feature additions, behavior changes, large refactors. Pure cleanup only.

## Fix claudewatcher stale heuristic + store agent PID in state

`claudewatcher`'s silence heuristic (`working/waiting + 15s no JSONL growth → stale`) misfires for extended-thinking turns. During pure thinking, claude emits ZERO JSONL entries — thinking blocks are buffered until the model emits the next text or tool_use block. Result: a 7+ minute thinking turn flips to `stale` at the 15s mark even though the agent is actively computing. Caught live today — `935` showed `stale` while genuinely mid-thinking on a codex-review triage. The new (fixed) `agentboss wait` correctly does NOT return on `stale`, so it just hangs forever waiting for an idle that never comes.

The proper signal for "is the agent actually alive vs. wedged?" is the **PID of the agent process** (the supervised CLI — `claude`, `codex`, etc.). Today's state.json doesn't store it. Storing the PID lets the watcher (and `ls`) confirm "process alive + in-progress turn = thinking, leave it alone" vs. "process dead or stuck = real stale."

- [x] implement and verify
  - add `AgentPID int` to `StateData` (statefile.go) — populated by the supervisor on first publish, doesn't change for the lifetime of the supervisor
  - the supervisor already knows the child PID (`exec.Cmd.Process.Pid` from the spawned `claude --dangerously-skip-permissions` process); plumb it into the initial state event
  - **note on bunx-style wrappers**: cc6's earlier work flagged that the supervised PID is the wrapper, not the real claude process. For `claude --dangerously-skip-permissions` (no wrapper) the supervised PID IS claude. For wrapped invocations the agent might still be alive even if the wrapper exited. Document this — for now, store the supervised PID and treat "supervised PID alive" as the proxy signal
  - in `claudewatcher.go`, track whether the current turn is "in progress" (saw an assistant entry, not yet seen `stop_reason: end_turn` or equivalent)
  - new stale logic: only flip `working/waiting → stale` if (a) JSONL hasn't grown for the budget AND (b) the agent PID is dead OR (c) no in-progress turn AND silent for an extended window. While the turn is in-progress and the PID is alive, silence is expected — stay in `working`
  - update the existing `processNewBytes` / silence-heuristic unit tests
  - new test cases: (1) in-progress turn + 30s silence + PID alive → stays `working`, (2) in-progress turn + PID dead → flips to `stale` immediately, (3) no in-progress turn + 60s silence + PID alive → flips to `stale` after the extended window
  - regression: spawn an agent, run extended thinking for 5+ minutes, confirm `agentboss ls` reports `working` the whole time
  - coordinate with the parallel "Show state age" section since both touch `claudewatcher.go` + `StateData`

## Show state age + finer-grained claude states in `agentboss ls` / `status`

Two related improvements to the boss's visibility into agent state:

**(1) Time-in-current-state.** `agentboss ls` shows process AGE (time since spawn) but not how long the process has been in its CURRENT state. The boss needs the second number — "working" for 12 minutes is a real long-thinking turn worth waiting on; "working" for 30 seconds is fine to leave alone. Today the boss has to eyeball pane content for "Contemplating… (Xm)" which is fragile. The supervisor's EventBus already publishes state transitions with timestamps — just expose them.

**(2) Two-level state model.** Today the supervisor publishes one flat `state` string (`working`/`idle`/`waiting`/`stale`/`child_exited`). Add a second optional field — `detail` — for agent-specific substate that the boss can show but doesn't have to reason about. The boss's logic still keys off the high-level `state` (uniform across agents); `detail` is for human/boss visibility only.

- **High-level state** (uniform, boss-portable): `working` / `idle` / `waiting` / `stale` / `child_exited`. Unchanged. This is what the boss's `wait` / `ls` filtering reads.
- **Detailed state** (agent-specific, optional): for claude, derived from the JSONL assistant content block type — `thinking` (extended thinking), `writing` (text streaming), `tool_use` (running a tool), and the per-tool name if available. For codex, no detail (its lifecycle events don't expose this granularity). For other agents, whatever they expose. The watchers fill in `detail` alongside `state`.

This lets the boss tell a useful pattern: a 10-minute high-level `working` with `detail: thinking` is normal extended reasoning; a 10-minute `working` with `detail: tool_use(Bash)` on the same tool may be a loop.

Schema:

```json
{
  "state": "working",
  "detail": "thinking",
  "since": "2026-04-08T15:53:42Z"
}
```

- [x] implement and verify
  - add `Detail string` and `LastTransitionAt time.Time` to the supervisor's `StateData` (events.go) — both optional/zero-valued by default
  - update EventBus + state.json + SSE wire format to carry both. Backward-compat: missing detail = empty string is fine
  - track `LastTransitionAt` in the cached state, updated only when `state` (high-level) changes — NOT on every detail change, otherwise the "time in current state" number resets too often
  - extend `claudewatcher.classifyEntry` to return `(state, detail)` — high-level state stays as today, detail comes from the assistant content block `type` (or tool name for `tool_use`)
  - keep `idle` / `waiting` / `stale` / `child_exited` at the high-level layer unchanged
  - codex watcher: leave detail empty (no granularity available from its lifecycle events for v1)
  - `agentboss ls` grows a STATE_AGE column (e.g. `working 4m32s`); if detail is present, render as `working/thinking 4m32s` or similar
  - `agentboss <key> status` non-quiet variant prints `<state> [detail] <age>`; `-q` keeps the current terse one-word output for scripting compat
  - update existing `classifyEntry` unit tests for the new `(state, detail)` return; add a thinking-block test case
  - regression: spawn an agent, send a task, observe `agentboss ls` cycling through detail = `thinking → tool_use → writing → (none on idle)` with the high-level state mostly staying `working` until the final `idle`
  - coordinate with the parallel "Switch agentboss ls" section — both touch the same ls/state.json area; rebase whichever lands second

## Refactor watchers to share a `tailFile` helper

`claudewatcher.go` and `codexwatcher.go` each duplicate ~30 lines of size-based incremental file-tail loop. Extract into a shared `tailFile(ctx, path, onBytes func([]byte))` helper. The state-machine + initial-state + silence-heuristic logic stays per-watcher (it's specific to each agent's transcript format). Low priority — only do this when a third watcher (amp? opencode?) is on the way; until then, the duplication is fine.

- [x] implement and verify
  - extract `tailFile` into its own file (or supervisor.go)
  - both watchers call it; per-watcher state machines unchanged
  - existing classifyEntry / classifyCodexEntry unit tests still pass
  - new unit test for `tailFile` against a synthetic growing file

## Port `tmpfile` into shell-helper + stow a shim

The `tmpfile` helper used to be a standalone Python script at `~/.local/bin/tmpfile`, outside the dotfiles repo and invisible to `pymake` / `dotfile_stow.py`. Caught during `fix-tmpfile-encoded-path-readability` (15:46) — the agent edited it in place outside the repo.

Ported the logic into `shell-helper` as a `tmpfile` subcommand (canonical, importable, testable), and added a shim at `dotfiles/.local/bin/tmpfile` (`exec shell-helper tmpfile "$@"`) so the bare `tmpfile` command keeps working from any subprocess on `$PATH`.

- [x] add `shell_helper/tmpfile.py` with `tmpfile_path()` helper + typer command
- [x] wire `app.command("tmpfile")` in `main.py`
- [x] create executable shim at `dotfiles/.local/bin/tmpfile`
- [x] smoke test: `shell-helper tmpfile foo.txt` outputs the expected timestamped path
- [x] swap in the symlink: `rm ~/.local/bin/tmpfile && (cd ~/github.com/hayeah/dotfiles && pymake)`
- [x] verify: `which tmpfile` points at `~/.local/bin/tmpfile` (the symlink), and `tmpfile foo.txt` from a fresh shell still works

## Add `agentboss state <key>` command + update boss skill docs

After the `switch-agentboss-ls` refactor, there is no per-key state read. `agentboss <key> status -q` was removed and `agentboss ls` is the only way to find out what state a session is in — the wrong shape for "what state is THIS key in", which is the boss's most common query (every check-in, the boss looks up one specific session by its key). Today the boss has to run `agentboss ls` and grep/parse for one row.

This bit the boss live (16:25 friction): "All my poll loops were using the dead syntax." BOSS_LOOP.md and SKILL.md still reference the removed command in several places (crash-recovery loop, "Talking to a running subagent", "Check in" rules). Fix the CLI gap and the doc rot in one go — the docs can't be cleaned up properly until there's a per-key reader to point at.

- [x] add `agentboss state <key>` subcommand (shipped by 955, merged as `d1471f2`; reuses `deps.stateFS` so it can't drift from `ls`; `--json` for full record; `SilenceUsage:true` for clean unknown-key errors; unit-tested via `TestFormatStateLine`)
- [x] update boss skill docs to use the new CLI surface
  - grep `skills/boss/` for `status -q` and `agentboss <key> status`, replace with the current idiom:
    - per-session reads → `agentboss state <key>`
    - listing all sessions → `agentboss ls`
    - waiting on transitions → `agentboss wait <key> --timeout N`
  - update the crash-recovery snippet in BOSS_LOOP.md "Crash recovery"
  - update SKILL.md "Talking to a running subagent" → "Inspect state"
  - update BOSS_LOOP.md "Check in" rules wherever they still say `agentboss status`
  - sanity-check the agentboss `--help` output matches what the docs claim

## Document worktree-cwd footgun in AGENT_LOOP.md

In WORKTREE mode, absolute paths under `/Users/me/github.com/hayeah/<repo>/...` resolve to the **main checkout**, not the worktree at `.worktrees/<slug>/...`. Easy to mix up when grepping with absolute paths but editing with the worktree in mind — the agent ends up editing the wrong tree and the changes never make it into the section's branch. Caught in the `fix-tmpfile-encoded-path-readability` section (15:46) and explicitly flagged as "worth adding to AGENT_LOOP.md".

- [x] added "Worktree path discipline" subsection to AGENT_LOOP.md "What you do" — covers the rule, the failure mode, and a pre-edit `pwd` check

## agentboss polish bundle (low-priority follow-ups)

Small papercuts surfaced across multiple sections that don't justify their own section each. Bundle them. Pure cleanup, no behavior change.

- [x] doc comment on `EventBus.Subscribe` warning that the first event is a cached snapshot, not a real transition (the `fix-agentboss-wait` section ate a half-day on this — next SSE consumer will hit the same trap unless we mark it)
- [x] contributor-guide note (or comment in `cli/agentboss/*_test.go`) about the macOS unix-socket path-length cap (~104 bytes); recommend `os.MkdirTemp("/tmp", "ab")` over `t.TempDir()` for any test that opens a unix socket
- [x] re-run `go generate ./cli/agentboss` (need `wire` in PATH first — `go install github.com/google/wire/cmd/wire@latest`) and confirm `wire_gen.go` matches the hand-edited version from the `switch-agentboss-ls` section. Diff should be empty.
- [x] consider deleting the `readStateFiles(stateDir)` "unused currently" dead-code path in `status.go` if it's still around — flagged in the af5 trouble report

## Build a `boss` CLI to mechanize the boss-loop hands

The boss skill currently asks the boss session (an LLM) to carry out a long, error-prone manual sequence on every spawn / lgtm / teardown / tick. The hands should be in a tool; the brain (judgment calls) stays with the boss LLM. Today's session ran the loop end-to-end manually for 3 parallel sections, surfacing several papercuts a CLI could prevent.

Spec: `$MDNOTES_ROOT/2026-04-08/boss-cli-spec_claude.md` — read this first. It covers the why, the inputs to the design (existing skill docs, friction.md, today's spawn script), the sketched command surface (`spawn` / `state` / `check` / `send` / `wait` / `lgtm` / `close` / `harvest` / `tick` / `recover`), the safety properties to bake in from real incidents, the brain/hands split, the integration / install plan, and the migration plan for `skills/boss/`.

- [x] design, implement, dogfood, and migrate the boss-skill docs to the new CLI per the spec
  - refine the spec into a concrete implementation plan (language, repo location, briefing template, meta.json schema)
  - implement
  - dogfood by re-running a multi-section spawn → lgtm → close → harvest sequence using only `boss <verb>` (no manual `git` / `agentboss` / `jq`)
  - rewrite `skills/boss/SKILL.md` and `BOSS_LOOP.md` to call `boss <verb>` instead of inlining shell snippets
  - cross-check `AGENT_LOOP.md` for any `agentboss <key>` references the agent might still call (probably fine — it's the agent contract, not the boss hands)

## Remove `agentboss run --key` and consolidate to a single id per session

Every agentboss session today has TWO names: a `key` (e.g. `473` when auto-generated, or `claude-stale-test` when the user passes `--key`) AND a separate `short_id` (e.g. `3a8`, `081`). Both forms resolve to the same store entry via `store.Resolve`. Caught live: the boss spawned without `--key`, agentboss generated `key=473`, `agentboss state 473 --json` reports `"key": "473"`, but `agentboss state 3a8 --json` *also* returns the same record — and `agentboss wait 473` errored with "waiting for 3a8 to become idle", silently leaking the internal alias. The user never asked for two names, never saw `3a8` in any normal output, and reasonably assumed it must be invalid.

Root cause of the dual-id: `--key` lets users pick a friendly name like `claude-stale-test`, but that name can't be used as a tmux window name (length/charset constraints), so agentboss has to mint a separate `short_id` for the tmux/internal layer. Once that escape hatch exists, every session — even auto-keyed ones — carries the dual identity. Wait error messages, internal logs, and at least one CLI surface use the short_id instead of the user-facing key, leaking the duality.

Fix: remove `--key` entirely. agentboss always generates the identifier itself, picking something that's *also* a valid tmux window name (3-char base32 like `3a8` is fine — tmux accepts it). Then `key`, `short_id`, and tmux window name collapse to one string. Every CLI surface uses that single id.

- [x] remove `--key`, collapse `short_id` + `key` into one auto-generated id, fix every leak
  - delete the `--key` flag and its plumbing in `agentboss run`
  - generator must produce ids that are also valid tmux window names (alphanumeric, ~3-4 chars — current auto-keys like `473`/`955`/`88a` already qualify)
  - drop `short_id` from `agentboss run` JSON output, state.json schema, and `store.Resolve` (single lookup table)
  - audit every CLI surface for short_id leakage; the known offender is `agentboss wait`'s timeout message ("waiting for 3a8 to become idle" when the user passed `473`)
  - update `skills/boss/SKILL.md` to drop the now-redundant "Do not pass `--key`" caveat
  - regression: spawn a session, confirm `key`, tmux window name, and the wait timeout message all echo the same string; spawn 5 in quick succession with no collision

Out of scope: backwards-compat for tools that pass `--key` today. There are none beyond a one-off command in 473's worklog — clean break is fine.

## Fix `tmpfile` encoded-path readability

The `tmpfile` helper creates dirs at `~/Dropbox/notes/<date>/tmp/<HHMMSS.ms>-<title>`. The `.` in the millisecond suffix gets encoded by claude as `-` in transcript paths (`~/.claude/projects/-Users-me-Dropbox-notes-2026-04-08-tmp-143052-283-foo`), making encoded dirs hard to recognize visually when scanning `ls ~/.claude/projects/`. Either drop the `.` separator or replace with something that survives encoding.

- [x] implement and verify
  - find the helper (`which tmpfile`), update the timestamp format
  - existing usages keep working — it's referenced in CLAUDE.md, AGENTS.md, and BOSS_LOOP.md
  - sanity-check: create a tmpfile, look at the encoded path under `~/.claude/projects/` after a claude run from that dir, confirm it's recognizable

## SwiftUI List demo view in reader-swiftui sandbox

Build a `ListDemoView` in `~/github.com/hayeah/reader-swiftui/apps/sandbox` that exercises SwiftUI's `List` in several different visual/interaction modes so the human can eyeball them side by side. Use this as a learning surface for what `List` can do (plain / inset / inset-grouped / sidebar styles, swipe actions, sections, selection, edit mode, etc.).

Use the `/swiftui` skill (`skills/swiftui/SKILL.md`) for project conventions, the SwiftUITap agent SDK for driving the running app, and the screenshot workflow.

The view has a toolbar button in the bottom-right that opens a settings sheet. Changing settings in the sheet swaps the list mode live so flipping through them is fast.

- [x] implement and verify
  - new `ListDemoView` (and any supporting types) under `apps/sandbox`
  - bottom-right toolbar button opens a settings sheet (`.sheet(...)`) with controls for whichever knobs you decide to expose — at minimum `listStyle` (plain, inset, insetGrouped, sidebar, grouped) and a couple of content variants (flat vs. sectioned, with/without swipe actions, edit mode on/off)
  - changing a setting in the sheet updates the underlying `List` immediately
  - include a `#Preview` block that renders the view (multiple previews are fine if it helps show the modes)
  - **evidence**: drive the running app via the swiftui agent / sim and capture screenshots of the view in at least 3-4 distinct list modes. Save them under the workspace `tmp/` dir and link them from `## Evidence`. The boss wants to actually see the different modes, not just "it builds".

## Fix `agentboss send` long-paste submit race upstream

Upstream work on `~/github.com/hayeah/agentboss`. Use a worktree off `master`. The bug:

`agentboss send <key> "<long multi-line text>"` calls `tmux.SendText` (which uses `send-keys -l`), sleeps 100ms, then sends `Enter` via `send-keys`. For a multi-line paste, claude code's TUI is still finalizing the `[Pasted text #N +X lines]` placeholder when the Enter arrives — the Enter gets absorbed into the paste buffer (becomes a newline within the boxed paste) instead of submitting. The text sits in the input forever.

Caught live: spawning a 33-line briefing via the boss CLI dropped the briefing into the input box and never submitted it. The boss skill currently has a Python workaround in `skills/boss/src/boss/agentboss.py:submit()` that:

  1. sends text with `--no-enter`
  2. polls the pane until the input area shows the buffered content (paste placeholder)
  3. sends Enter via `--keys` as a separate call
  4. verifies the input cleared, retries up to 4× with growing delays

We want this same robustness inside `agentboss send` itself so every caller (not just the boss CLI) gets it for free. After the upstream fix lands, the Python `submit()` wrapper collapses back to a plain `send`.

Meta keys are NOT a fix — claude code treats Shift+Enter / Option+Enter as "newline within input", not "submit". The only mechanism is plain Enter, sent at the right time.

- [x] implement and verify
  - in `cli/agentboss/send.go` (and/or `tmux.go` / `boss.go`), change the `sendFn` flow so that for non-`--no-enter` sends:
    - send the text with `SendText`
    - poll the pane bottom for the input prompt to show buffered content (paste placeholder OR literal text), with a short deadline (~3s)
    - send `Enter` via `SendKeys`
    - re-capture the pane and verify the input cleared (no leftover `[Pasted text` or buffered chars after the prompt)
    - if not cleared, send another Enter, with a small growing delay between attempts (~3-4 retries total)
    - if still not cleared after retries, return an error so the caller knows the submission failed
  - the existing 100ms-then-Enter path is fine for short single-line text; consider whether to keep it as a fast path or just always use the robust path. Lean toward "always robust" unless there's a measurable latency hit
  - keep `--no-enter` and `--keys` semantics unchanged
  - **regression test 1** (hard requirement — this is exactly the bug we're fixing): a Go test that spawns a real claude session, sends a 30+ line multi-line message, and asserts the message was actually submitted (input cleared, claude visible-state shows it processing). A unit test against a fake tmux is also fine if e2e is hard to set up, but cover the multi-line case explicitly
  - **regression test 2**: short single-line send still works and doesn't add noticeable latency
  - update the Python wrapper at `skills/boss/src/boss/agentboss.py` afterwards: collapse `submit()` back to a thin alias for `send()` (or delete it and have callers use `send` directly), and update `boss spawn` in `skills/boss/src/boss/main.py` to call `send()` instead of `submit()`. Reinstall via `uv tool install -e .` and spot-check by spawning a fresh boss section and confirming the briefing submits

- [x] fix the false-negative race in the submit verifier (reopened 2026-04-09)

  After the original implementation landed, every multi-line `agentboss send` against a real claude session **errors out** with `submit: input still buffered after 4 Enter attempts` even though **the message did get submitted on the very first Enter**. Reproduced live in three back-to-back boss spawns and confirmed every time by inspecting `agentboss output <id>` immediately after the failing send: the message is in the input history above an empty `❯` prompt and claude is processing it. The error is harmless to the user (the message went through) but it's noise on every spawn and it makes failure modes ambiguous — a real failure would look exactly the same as the spurious one.

  Root cause analysis (untested theory worth verifying first):

  - `tmux capture-pane` is asynchronous relative to the actual terminal state. After `send-keys Enter`, claude's input clears within a millisecond, but the next `capture-pane` may return a frame from before the submit landed.
  - The verifier sees "input still buffered" → retries Enter → Enter goes into a now-empty input → claude renders a literal newline at the prompt → pane STILL doesn't match the verifier's "empty input" expectation → retry again → 4 retries exhausted → error.

  Three fix ideas, in order of preference:

  - **Transcript-tail approach (PREFERRED)**: claude code writes a JSONL session transcript at `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl`. Every user message that gets submitted appears as a `user` entry in that file. The claudewatcher (`claudewatcher.go`) ALREADY tails this file for state detection — the infrastructure is there. Use it as the success signal:
    - Snapshot the transcript file size BEFORE sending
    - After `send-keys Enter`, tail the transcript for new entries (or just for any byte growth past the bookmark size)
    - If a new `user` entry appears with the submitted content (or just any new entry, depending on how strict we want to be), declare success
    - Timeout if nothing appears within ~1-2 seconds → real failure
    - This is the **ground truth**: if the message is in claude's transcript, claude received it. Period. No capture-pane lag, no terminal-state heuristics.
    - For codex sessions, mirror with the codex transcript path (codexwatcher already tails it).
  - **Bookmark + diff fallback**: if the transcript path is unavailable for some reason (no detector, transcript not found yet), fall back to capturing the pane content BEFORE the first Enter and comparing it byte-for-byte after. Any change at all = the Enter took effect → return success. Less precise than the transcript signal but doesn't false-negative the way "input is empty?" matching does.
  - **State-transition approach**: watch the supervisor's `session.json` for an `idle → working` transition. Probably redundant once the transcript-tail approach is in.

  - [ ] implement and verify
    - first, **reproduce + characterize** the race: write a small Go harness that calls `boss.Submit` against a fresh claude session with a 33-line message and dumps both pane snapshots AND transcript bytes at each verifier iteration. Confirm the theory before changing any production code
    - implement the **transcript-tail approach** in `submit.go` (via `boss.go` / claudewatcher infrastructure for the JSONL path resolution). Bookmark transcript size before send, poll for growth after Enter, return success on first byte growth (or first new `user` entry, your call on strictness)
    - keep a small bookmark+diff fallback path for the case when no transcript is available (e.g. session_id not yet discovered, or detector is `none`)
    - **regression**: 33-line message submits without error AND without warning (exit 0, no stderr noise)
    - **regression**: 1-line message submits without error
    - **regression**: actual broken cases (e.g. tmux pane killed mid-send, transcript file gone) still return a real error so the caller knows
    - update the unit tests in `submit_test.go` for the new state machine
    - dogfood: spawn a fresh boss section via `boss spawn`, confirm zero "submit failed" warnings

  Note: this section is being reopened after the original work was lgtm'd and merged. Boss already killed the agent that did the original work; the workspace dir at `$BOSS_ROOT/fix-agentboss-send-long-paste-submit-race-upstream/` is still around with the prior worklog as context. Read the prior `## Trouble report` and `## Evidence` sections to see what 258 already verified and what the test harness looked like before reproducing the new bug.

## Drop the agentboss SQLite db, walk per-session dirs instead

Upstream work on `~/github.com/hayeah/agentboss`. **Depends on `remove-agentboss-run-key-and-consolidate-to-a-single-id-per-session` landing first** — do not start until that section is merged. The new id-only schema is the simplification this builds on.

Today agentboss has two storage layers:

- **`~/.agentboss/agentboss.db`** (SQLite) — the process registry. One row per session: id, cwd, cmd, session_id, tmux target, created_at. Used by `agentboss ls` to enumerate, `store.Resolve(name)` to look up by id/prefix, the `IsAlive` prune sweep, and the per-session-dir hash mapping.
- **`~/.agentboss/<hash>/`** — per-session directories holding `state.json`, log files, the SSE event-bus unix socket, and file locks. This layer is the *hot path* — `state.json` is rewritten many times per second by the supervisor goroutine.

The DB exists because at one point an `index → directory` mapping table was the obvious thing to reach for. **But the per-session dirs already encode the registry on disk.** If `~/.agentboss/<hash>/meta.json` (or whatever the per-session metadata file ends up named) holds the same fields the SQLite row holds, the DB is pure duplication.

We just paid the cost of the DB live: the `--key` removal section's destructive migration 2 ran against the live `agentboss.db`, ate the running agent's own row, and made the agent invisible to `agentboss ls` / `state` / `wait` for the rest of its session. Bootstrap fragility — a file-based registry would have been resilient under the same change because old per-session dirs are still on disk and a careful migration tool can read them.

The plan:

- Move every field currently in the SQLite row into a per-session `meta.json` (or similar) inside `~/.agentboss/<hash>/`. The supervisor writes it on first publish, never modifies it again (immutable for the lifetime of the session — the *mutable* state stays in `state.json`).
- Replace `ProcessStore` (currently SQLite-backed) with a flat-file walker: `List()` = `os.ReadDir(~/.agentboss/)` + read each `meta.json`; `Resolve(name)` = walk + find by id; `Save()` = atomic write of `meta.json` once at session creation; `Delete()` = `os.RemoveAll(~/.agentboss/<hash>/)`.
- File locks (already used for state.json) cover the rare write contention. With ≤ tens of sessions and rare writes, scanning the dir on each `ls` call is fine — `state.json` reads are way hotter and we already do those file-by-file.
- Drop `agentboss/db/` entirely, drop the migration framework, drop the SQLite dependency from `go.mod`.
- The `IsAlive` prune sweep moves from "delete row + remove state file" to "delete the per-session dir if the tmux pane / process is gone".

- [x] implement and verify
  - design a `meta.json` schema covering the fields currently in the `processes` SQLite table (id, cwd, cmd, session_id, tmux target, detector, created_at). One immutable file per session, written once on supervisor start
  - reimplement `ProcessStore` as a flat-file walker over `~/.agentboss/`. Tests against a tmpdir-rooted store
  - migrate the `IsAlive` prune sweep from row-based to dir-based — when a session is dead, `os.RemoveAll(~/.agentboss/<hash>/)` is the cleanup
  - delete `agentboss/db/`, drop the SQLite dep from `go.mod`, drop migration code
  - update every CLI command that touches `deps.store` — should be a no-op rename if the interface stays the same
  - **migration story for existing users**: write a one-shot tool (or first-run shim) that reads `~/.agentboss/agentboss.db` if it exists, writes a `meta.json` into each per-session dir, then renames `agentboss.db` to `agentboss.db.legacy` so users can recover if anything goes wrong. After the tool runs once, the DB is unused and can be removed manually.
  - **regression**: spawn 3+ sessions, kill some via `kill -9`, run `agentboss ls`, confirm the dead ones are pruned and the live ones still resolve by id and by short prefix
  - **regression**: spawn a session, restart agentboss/the tmux daemon, run `agentboss ls`, confirm the session still resolves (per-session dir survived)
  - update `skills/boss/src/boss/agentboss.py` if it makes any assumption about a SQLite-backed store (probably not — it only calls the CLI)
  - dogfood by running a real boss section through `boss spawn` / `boss ls` / `boss lgtm` after the rewrite

## Add `pymake setup` + `.worktrees.setup` + wire SwiftUITap in reader-swiftui sandbox

Work in `~/github.com/hayeah/reader-swiftui`. Two things that bit the ListDemo agent and will bite every future worktree-mode agent in this repo.

**1. `pymake setup` task + `.worktrees.setup` hook.** Two gitignored build prerequisites must exist before `xcodebuild` will build any scheme:

- `BookReader.xcodeproj` — regenerated via `xcodegen generate`
- `Sources/BookReaderKit/Resources/WebContent/` — a `pymake web_bundle` artifact, not checked in

Add a `setup` task to the repo's pymake config that runs both steps (xcodegen + copy/symlink WebContent from wherever the canonical source is — probably main checkout or a build step). Then add a `.worktrees.setup` hook at the repo root that just runs `pymake setup`. The hook is the thin shim; the pymake task is the canonical logic that humans and agents can both call.

**2. Wire SwiftUITap into the Sandbox target.** The ListDemo agent couldn't use tap-then-screenshot evidence because Sandbox doesn't have `@SwiftUITap @Observable` AppState wired in. The workaround (env-var-driven defaults + `SIMCTL_CHILD_*` relaunch) works for "show me a matrix of visual modes" but can't do "tap the gear, screenshot the sheet" which is the natural interactive evidence pattern.

Wire SwiftUITap into `SandboxApp.swift`:
- Add an `@Observable` AppState (or reuse one if it already exists)
- Call `SwiftUITap.poll(...)` from the root scene
- Confirm the SwiftUITap agent can reach the Sandbox from a fresh build + sim install

Use the `/swiftui` skill for conventions.

- [x] add `pymake setup` task + `.worktrees.setup` hook
  - the setup task should be idempotent (safe to re-run)
  - verify: `git worktree add .worktrees/test-setup -b test-setup master && cd .worktrees/test-setup && pymake setup && xcodebuild -scheme Sandbox -destination 'platform=iOS Simulator,name=iPhone 17 Pro' build` succeeds from a clean worktree
  - clean up the test worktree after verification
- [x] wire SwiftUITap into the Sandbox target
  - the existing `DemoPickerView` is already the root (switched during the ListDemo section — intentional)
  - verify: build Sandbox, install on sim, confirm SwiftUITap agent can connect and issue a tap + screenshot
  - capture a screenshot of the ListDemoView settings sheet (the one the ListDemo agent couldn't capture via env vars) as evidence

## Integrate KIF touch synthesis into SwiftUITap

Work in `~/github.com/hayeah/SwiftUITap`. Read the KIF research note at `/Users/me/Dropbox/notes/2026-04-09/kif-embedded-touch-synthesis_claude.md` for background. The KIF source is at `~/github.com/kif-framework/KIF`.

Add KIF's touch synthesis to SwiftUITap so agents can inject real UIKit touches via the relay server. Extract just the core touch files from KIF (no XCTest dependency) and expose them through the existing SwiftUITap command protocol.

Commands to add (accessed via the relay server):
- `.kif.tap x y` — tap at screen coordinates
- `.kif.swipe x1 y1 x2 y2 duration` — swipe from point to point
- `.kif.longpress x y duration` — long press at coordinates
- `.kif.type text` — type text via keyboard synthesis

This should work on both simulator and real devices (KIF is in-process, no simulator-specific APIs).

- [x] implement and verify
  - extract KIF touch synthesis core files into SwiftUITap (UITouch-KIFAdditions, UIEvent+KIFAdditions, IOHIDEvent+KIF, etc.)
  - wire up `.kif.tap`, `.kif.swipe`, `.kif.longpress`, `.kif.type` commands in the relay server
  - build a test app that includes SwiftUITap, install on sim
  - test: `swiftui-tap kif.tap 150 300` taps at coordinates, verify with a button that changes state
  - test: `swiftui-tap kif.swipe 150 400 150 100 0.3` scrolls content
  - evidence: screenshots before and after tap/swipe showing actual UI changes
  - **known limitation**: taps on SwiftUI buttons inside List (UICollectionView) don't work on iOS 26 — use `state call` for list items

## Investigate and analyze ev-winners dataset

Clone `https://github.com/nqureshi/ev-winners` to `~/github.com/nqureshi/ev-winners`. Investigate how `data/ev-winners.csv` is scraped/generated — read the scraping scripts, understand the data pipeline. Then load the CSV into DuckDB and do exploratory analysis (schema, row counts, distributions, interesting patterns). Also transition the project to use `uv` for dependency management.

- [ ] investigate and analyze
  - `git-quick-clone https://github.com/nqureshi/ev-winners`
  - read the scraping code to understand how the CSV is generated (what sources, what transformations)
  - load `data/ev-winners.csv` into DuckDB, explore the schema, do basic analysis (value distributions, top entries, time trends, any anomalies)
  - transition the project from whatever dep management it uses to `uv` (pyproject.toml, uv.lock)
  - write findings as a note in `$MDNOTES_ROOT/2026-04-10/ev-winners-analysis.md`

## SwiftUITap multi-device support

Work in `~/github.com/hayeah/SwiftUITap`. Support multiple simulators/devices connecting to a single relay server, routed by device UDID.

Changes needed:

**App side (polling):** When the app polls the relay server, it should include its device UDID in the request (e.g. query param or header). Use `ProcessInfo.processInfo.environment["SIMULATOR_UDID"]` on sim, or a passed-in env var for device builds.

**Relay server:** The server maintains per-device command queues. When a device polls with its UDID, it gets commands for that device only. State get/set/call are also routed by UDID.

**CLI (`swiftui-tap`):** Add `--udid` flag and `SWIFTUI_TAP_UDID` env var to route commands to a specific device. Default to the first/only connected device for backwards compat.

- [x] spec and implement
  - write a spec first (API changes, protocol, backwards compat)
  - modify the relay server to support per-UDID routing
  - modify the Swift polling to include UDID
  - modify the CLI to accept --udid / SWIFTUI_TAP_UDID
  - test: boot two sims, install the TodoList example on both, connect both to the same server, send commands to each independently via --udid
  - evidence: screenshots showing two sims with different state after targeted commands

## Resource leasing: agentboss lease + worktree refactor + iOS simulator

Three related pieces in one section. Work spans `~/github.com/hayeah/agentboss` and `~/github.com/hayeah/dotfiles`.

**Part 1: `agentboss lease` — session-scoped resource leasing**

The boss CLI's `.lease.json` + GC approach for worktree pools works but requires active garbage collection. agentboss already knows session liveness — leases should live there so they automatically expire when sessions die.

- `agentboss lease <key> <namespace>:<lease-key>` — register a lease (e.g. `worktree:hayeah/reader-swiftui_001`, `simulator:FE47576C-...`)
- `agentboss lease-release <key> <namespace>:<lease-key>` — explicit mid-session release
- `agentboss lease-list [--namespace <ns>]` — list live leases (only from live sessions)
- `agentboss lease-check <namespace>:<lease-key>` — is this resource held? Returns holder key or exits non-zero

Leases stored in session metadata. When a session dies/is pruned, its leases vanish. Scripts (boss checkout) still allocate resources — agentboss just tracks liveness.

**Part 2: Refactor boss checkout to use agentboss lease**

Replace `.lease.json` files in pool slots with `agentboss lease` calls. `boss checkout` calls `agentboss lease-check worktree:...` to find free slots instead of scanning `.lease.json` files. No more GC sweeps.

**Part 3: iOS simulator leasing via `boss checkout --ios-simulator`**

The agent explicitly requests a sim. `boss checkout --ios-simulator` clones a base device (or reuses one), boots it, registers `agentboss lease <key> simulator:<UDID>`, and stores the UDID in `.boss.json`. The UDID flows to SwiftUITap via `SWIFTUI_TAP_UDID` env var.

```bash
# How multiple sims work under the hood
xcrun simctl clone "iPhone 17 Pro" "agent-000"
xcrun simctl boot <UDID>
xcodebuild -destination 'id=<UDID>' build
xcrun simctl install <UDID> path/to/app
xcrun simctl launch <UDID> com.example.app
# Each sim uses ~1-2GB RAM; 3-4 concurrent fine on M4 32GB+
```

- [x] implement agentboss lease commands (Part 1)
  - add `leases []string` to session metadata
  - implement `lease`, `lease-release`, `lease-list`, `lease-check` subcommands
  - regression: spawn, lease, kill, confirm lease gone
- [x] refactor boss checkout to use agentboss lease (Part 2)
  - replace `.lease.json` with `agentboss lease-check` / `agentboss lease`
  - update `boss lgtm` release path
- [x] add `boss checkout --ios-simulator` (Part 3)
  - implement sim clone/boot/lease in pool.py or sim.py
  - store UDID in `.boss.json`, pass via `SWIFTUI_TAP_UDID`
  - update AGENT_LOOP.md with note about leasing sims
  - test: two agents, same iOS repo, different sim UDIDs, independent builds

## Reorganize cross-language convention libraries under libs/

Spec: `$MDNOTES_ROOT/2026-04-10/cross-language-conventions-spec_claude.md` — read this first.

Move `hayeah/`, `hayeah-ts/`, `golib/` under `libs/`. Each module gets a directory with a `README.md` spec. Python is the canonical implementation. Shared test vectors go in `libs/testdata/`. Create a `libs/README.md` index with TLDRs and usage examples for each module. Write new shortid and config specs. Extract agentboss shortid into the shared lib.

- [x] implement per the spec
  - rename `hayeah/` → `libs/hayeah-py/`, `hayeah-ts/` → `libs/hayeah-ts/`, `golib/` → `libs/hayeah-go/`
  - move spec docs into per-module `README.md` files
  - move shared test data to `libs/testdata/`
  - create `libs/README.md` index
  - write new specs for `config` and `shortid`
  - update imports / references across the repo
  - update style guide skills to reference libs

## Add `boss add` command for appending new sections

Work in `~/github.com/hayeah/dotfiles/skills/boss/src/boss/`. Add a `boss add` command that appends a new section to the boss doc with date grouping.

Usage:
```bash
boss add <<'EOF'
## Fix toolbar toggle regression

Work in ~/github.com/hayeah/reader-swiftui.

- [ ] investigate and fix
EOF
```

Behavior:
- Read stdin for the section content (must start with `## `)
- Slugify the header and check uniqueness against existing sections in the boss doc
- If today's date header (`# YYYY-MM-DD`) is not already the last date header in the file, append it
- Append the section under today's date header
- `--boss-doc` flag for non-default boss doc path (same as other commands)

- [x] implement and verify
  - add `boss add` command in `main.py`
  - reuse `bossdoc.py` slug logic for uniqueness check
  - test: `boss add` twice on same day — only one date header. Add on new day — new date header. Duplicate slug — error.

## Tidy up libs/ — consistent modules across all 3 languages

Work in `~/github.com/hayeah/dotfiles/libs/`. Python is already well-organized. TypeScript and Go need work.

**hayeah-ts**: Currently `fzfmatch` is its own sub-package with its own `package.json` — should be a module within one top-level package. Target import path: `import { match } from "hayeah-ts/fzfmatch"`. Restructure to one package with subpath exports.

**All 3 languages** should have these modules with consistent import paths:
- `logger` — structured logging (Python: done, TS: done, Go: done)
- `fzfmatch` — fuzzy matcher (Python: done, TS: done, Go: reference at https://github.com/hayeah/fork2/tree/master/fzf — copy and adapt)
- `config` — single-envar config (Python: done, TS: missing, Go: missing)
- `shortid` — short ID generation + prefix resolve (Python: done, TS: missing, Go: missing)

Import paths should be consistent:
- Python: `from hayeah.core.fzfmatch import match`
- TypeScript: `import { match } from "hayeah-ts/fzfmatch"`
- Go: `import "github.com/hayeah/dotfiles/libs/hayeah-go/fzfmatch"`

For Go fzfmatch, clone https://github.com/hayeah/fork2 and use `fzf/` as a reference — copy the logic, adapt to the shared spec. Use `git-quick-clone`.

- [x] implement
  - restructure hayeah-ts: one package, subpath exports for each module
  - implement missing TS modules: config, shortid
  - implement missing Go modules: fzfmatch (from fork2 reference), config, shortid
  - all modules should pass against shared test vectors in `libs/testdata/`
  - update `libs/README.md` with consistent import examples

## Fix codex spawn reliability in agentboss

Upstream work on `~/github.com/hayeah/agentboss`. Two related issues:

**Issue 1: `can't find session: __agent` spam.** `agentboss run` uses `NewSessionOrWindow` which already creates the session if missing — but it prints `can't find session: __agent` to stderr first (from `HasSession`). This is cosmetic noise, not a real failure. Suppress it or make `HasSession` silent.

**Issue 2: `agentboss send` fails after spawn for slow-starting agents.** When `agentboss run` returns the JSON descriptor, the tmux window exists but the CLI inside it (codex via `bunx`) may not be ready for input yet. `boss spawn` currently adds a 10s sleep for non-claude agents — this is a workaround. The real fix: `agentboss run` should guarantee the agent is idle (ready for input) before returning, OR `agentboss send` should retry if the window/pane isn't ready.

Observed behavior:
- `boss spawn --agent codex` sometimes dies because the briefing send hits a window that's still initializing
- Manual spawn + 10s wait + send works reliably
- `agentboss run` spawner.go calls `Spawn()` — check if it waits for idle or returns immediately
- The codex detector may not detect idle correctly during the startup phase

- [x] investigate and fix
  - **first**: add `--tmux-session` flag to `agentboss run` (and/or `AGENTBOSS_TMUX_SESSION` env var) to override the default `__agent` session name. This lets tests use an isolated session like `__agent_test` without clobbering production agents. Update `boss.go` `AgentSession` to read from this config.
  - reproduce using a test session: `agentboss run --tmux-session __agent_test --detector codex -- bunx --bun @openai/codex --dangerously-bypass-approvals-and-sandbox`, immediately `agentboss send <key> "hello"` — does it fail?
  - read spawner.go: does `Spawn()` block until the agent reaches idle? If not, should it?
  - fix: either make `Spawn()` wait for idle, or make `send` retry on "can't find window"
  - suppress the `can't find session` stderr noise from `HasSession`
  - clean up test session after: `tmux kill-session -t __agent_test`
  - regression: spawn 5 codex agents in `__agent_test`, all succeed
  - **DO NOT kill or modify the `__agent` session** — other agents are running in it

## SwiftUITap polish: screenshots, computed properties, state get .

Work in `~/github.com/hayeah/SwiftUITap`. Three fixes:

- **Screenshot fix**: `TapInspectable.swift:82` uses `window.rootViewController?.view` which excludes presented sheets. Change to `window` so screenshots capture the full window including sheets/modals.
- **Computed property support**: The `@SwiftUITap` macro only generates `__tapGet`/`__tapSet` for stored properties. Computed properties with getters (and optionally setters) should also be exposed. Fix in `SwiftUITapMacro.swift` `extractProperties`.
- **`state get .`**: was broken by KIF debug leftover. Verify it works now (Dispatcher.swift line 30 looks correct). If still broken, fix it.

- [x] implement and verify
  - fix screenshot to use `window` instead of `rootViewController?.view`
  - update `extractProperties` in the macro to include computed properties
  - verify `state get .` returns the full snapshot (was a routing bug in dispatchBuiltin, not KIF leftover)
  - KIF already enabled by default in `poll()` — no change needed
  - test against the TodoList example: screenshot a sheet, get a computed property, `state get .`

## Detect codex usage limit as an agentboss state

Upstream work on `~/github.com/hayeah/agentboss`. When codex hits its usage limit, it displays `"You've hit your usage limit"` and stops processing input. The codexwatcher should detect this and publish a new state (e.g. `error` or `rate_limited`) so the boss loop knows the agent is dead and can act on it (respawn later, alert the user, etc.).

Currently codex just sits at the prompt showing the error — agentboss reports it as `idle`, which is misleading. The boss thinks the agent is ready for work when it's actually unable to process anything.

- [x] implement and verify
  - in `codexwatcher.go`, detect the `"You've hit your usage limit"` text in the pane output
  - publish a new state like `rate_limited` or `error` with detail `"usage_limit"`
  - `agentboss ls` and `agentboss state` should show this state clearly
  - `agentboss wait` should return on this state (it's a terminal condition, not transient idle)
  - test: spawn codex with an account at limit, confirm state shows `rate_limited`

## Verify worktree setup hook runs in reader-swiftui

Work in `~/github.com/hayeah/reader-swiftui`. Smoke test that the `.worktrees.setup` hook works with the new pooled worktree flow. The hook should run `pymake setup` which generates `BookReader.xcodeproj` and builds WebContent.

- [x] verify
  - `boss checkout ~/github.com/hayeah/reader-swiftui` from your workspace
  - confirm `BookReader.xcodeproj` exists in the worktree after checkout
  - confirm `Sources/BookReaderKit/Resources/WebContent/` exists
  - if either is missing, the hook didn't run — investigate and fix
  - evidence: `ls` showing both artifacts present in the pool slot
  - **fixed**: `.worktrees.setup` had `cd "$(dirname "$0")"` overriding the worktree cwd — removed it (`b2cb63a`)

## Tap to toggle toolbar in chapter reading view

Work in `~/github.com/hayeah/reader-swiftui`. In the chapter reading view, a light tap should toggle toolbar visibility (navigation bar, bottom bar, etc.). But scrolling and text selection must still work — taps that are part of a scroll gesture or text selection shouldn't trigger the toggle.

The standard iOS reader pattern: a single tap in the content area toggles chrome, but the gesture recognizer must not interfere with scroll or long-press-to-select. Look at how Apple Books / Kindle handle this — typically a `UITapGestureRecognizer` that requires the scroll view's pan gesture to fail, or a tap zone that excludes active selection.

- [x] investigate and implement
  - find how the chapter content is rendered (likely a WKWebView) and what gesture recognizers are already in play
  - add a tap gesture that toggles toolbar/navigation bar visibility
  - ensure scroll still works (tap gesture must not eat scroll/pan events)
  - ensure text selection still works (long press, drag handles)
  - evidence: screen recording or screenshots showing toolbar toggle, scrolling, and text selection all working
- [x] fix: toolbar toggle not working after merge
- [x] install IDB and test toolbar toggle with synthetic taps (IDB doesn't work with WKWebView)
- [ ] fix SwiftUITap init + test toolbar toggle with KIF touch
  - update SwiftUITap dependency in reader-swiftui to latest master (has KIF support)
  - build and install the reader app on sim
  - open a book to the reading view
  - use `swiftui-tap kif.tap X Y` to tap the content area and verify the toolbar toggles
  - use `swiftui-tap kif.tap` again to toggle it back
  - evidence: screenshots before and after tap showing toolbar visible/hidden
  - the JS bridge code and Swift handler are on master, but the feature doesn't work in the built app
  - likely the WebContent bundle is stale — rebuild via `pymake setup` or `pymake web_bundle` and verify
  - could also be a merge issue with the cover-image fix (both touch bridge.ts)
  - build, install on sim, verify tap-to-toggle actually works end-to-end

## Persist scroll position in book reading sessions

Work in `~/github.com/hayeah/reader-swiftui`. When reopening a book, the app remembers which book and chapter but loses the scroll position within the chapter. Fix it so scroll position is saved and restored.

- [x] investigate and fix
  - find how reading sessions are persisted (what state is saved today: book, chapter, anything else?)
  - find how the chapter content is rendered (WebView? ScrollView?) and how to capture/restore scroll offset
  - save scroll position as part of the session state
  - restore scroll position when reopening a book to the same chapter
  - evidence: open a book, scroll partway through a chapter, close and reopen — should return to the same position
- [x] fix: scroll position not restored after merge
- [x] verify scroll position restore works end-to-end with KIF tap
- [x] fix: reopening a book from Open Books list always scrolls to top
  - user reports scroll position not restoring when accessing a book from the Open Books tab — always shows scrolled to top
  - the prior codex verification was from the Library tab; the bug may be specific to the Open Books → reopen path
  - debug the open-book flow from OpenBooksView vs LibraryView — are they calling different methods? Is the scroll restore triggered in both paths?
  - use `swiftui-tap kif.tap` to navigate and `swiftui-tap state get` to inspect scroll values
  - read prior worklog at `$BOSS_ROOT/persist-scroll-position-in-book-reading-sessions/WORKLOG.md`
  - use codex agent
  - read prior worklog at `$BOSS_ROOT/persist-scroll-position-in-book-reading-sessions/WORKLOG.md`
  - read zxg's findings at `$BOSS_ROOT/tap-to-toggle-toolbar-in-chapter-reading-view/WORKLOG.md` (KIF tap works for SwiftUI buttons, not WKWebView content area)
  - build and install reader on sim, open a book, scroll partway, close and reopen — verify position restores
  - use `swiftui-tap kif.tap` to open books, navigate chapters, and `swiftui-tap state get` to inspect scroll position values
  - if scroll restore is broken, debug and fix
  - ReadingPositionStore and JS bridge setScrollFraction code are on master, but scroll position doesn't actually restore
  - debug: add logging to see if positions are being saved/loaded, check if setScrollFraction is called and the WebView actually scrolls
  - build, install on sim, verify scroll position persists across close/reopen

## Fix book cover images not loading in reader-swiftui

Work in `~/github.com/hayeah/reader-swiftui`. Book cover images aren't displaying — every book shows a loading error instead of its cover. Investigate why images from epubs aren't rendering and fix it.

- [x] investigate and fix
  - reproduce the issue: build and run on sim, observe the library view — covers should be broken/error state
  - trace the image loading path: where do covers come from (epub extraction? cached images? a URL?), how are they loaded into the view
  - find the root cause and fix it
  - evidence: screenshot of library view with covers actually showing

## Add pooled worktrees to boss

Fresh worktrees require expensive setup (pnpm install, xcodegen, Vite builds, Rust compiles). Instead of creating a disposable worktree per section, maintain a pool of pre-warmed numbered slots per repo. Agents lease a slot; `git reset --hard master` resets tracked files while build artifacts (gitignored/untracked) survive across leases.

Spec: `$MDNOTES_ROOT/2026-04-09/pooled-worktrees-spec.md`

Work in `~/github.com/hayeah/dotfiles`. The implementation is in `skills/boss/src/boss/`.

- [x] implement and verify
  - refactor `boss checkout` (in `main.py`) to use the pool/lease protocol instead of creating per-slug worktrees
  - on checkout: GC first (scan `.worktrees/NNN/.lease.json`, check `agentboss state <agent_id>`, reap dead leases), then find a free slot or grow a new one (`000`, `001`, ...), `git reset --hard master && git checkout -B <slug> master`, write `.lease.json` with `{"slug": "<slug>", "agent_id": "<id>"}`, symlink into workspace `repos/`
  - the agent_id comes from `.boss.json` in the workspace (already written by `boss spawn`)
  - if the repo has no `.worktrees/NNN` dirs yet (no pool), create `000` as the first slot and run `.worktrees.setup`
  - if a slot is already leased to this slug (re-checkout), reuse it without reset
  - refactor `boss lgtm` (in `lgtm.py`) to also do lease cleanup after merge: kill agent session, remove `repos/` symlinks, delete `.lease.json`, `git checkout --detach`, `git branch -d <slug>`
  - update AGENT_LOOP.md and SKILL.md if any worktree path conventions changed (`.worktrees/<slug>` → `.worktrees/NNN`)
  - test: `boss checkout` a repo twice with different slugs → gets different pool slots. Kill one agent → next checkout reaps it and reuses the slot

## Use plain list style and full-height sheets in bookreader-ios

Work in `~/github.com/hayeah/reader-swiftui`. The book reader's lists and outline sheet need visual tweaks.

**Lists → plain style, no inset.** `LibraryView` (all books) and `OpenBooksView` (open book sessions) currently use default list styling. Switch both to `.listStyle(.plain)` for a cleaner, edge-to-edge look.

**Outline sheet → full height on invoke.** `TableOfContentsSheet` (presented from `BookReaderView`) currently uses `.presentationDetents([.medium, .large])` which shows as half-height first. Change to `.presentationDetents([.large])` so it opens full-screen immediately — the outline is important enough to warrant the full sheet.

- [x] implement and verify
  - add `.listStyle(.plain)` to LibraryView and OpenBooksView
  - change TableOfContentsSheet's presentationDetents from `[.medium, .large]` to `[.large]`
  - add pull-to-refresh (`.refreshable`) to LibraryView — reload the book list on pull
  - build and run on sim, capture screenshots showing: (1) library list in plain style, (2) open books list in plain style, (3) outline sheet opening at full height, (4) pull-to-refresh in action on the library view

# 2026-04-10

## Implement Go supervisor library and devport run

Two deliverables in one section, both in Go:

**Part 1: `libs/hayeah-go/supervisor/`** — reusable supervisor library per the spec at `$MDNOTES_ROOT/2026-04-10/go-supervisor-lib-spec.md`. Dir flock for liveness, atomic state.json (supervisor + service sections), tmux window management via TmuxSpawn, Plugin interface, EventBus, unix socket SSE server. Also read the pattern doc at `$MDNOTES_ROOT/2026-04-10/supervisor-pattern.md`.

**Part 2: `devport run`** — new command in `~/github.com/hayeah/devportv2` that uses the supervisor library. Reads a TOML spec file, allocates free ports per service, creates supervisors with TmuxSpawn, writes `.devport.env` with port assignments. Per the spec at `$MDNOTES_ROOT/2026-04-10/dev-services-spec.md`.

`devport run` usage:
```
devport run devport.local.toml \
  --tmux-session agent-r19 \
  --state-dir .devport
```

- [x] implement supervisor library (Part 1)
  - Store (flat-file registry, dir flock, IsAlive probe)
  - Writer (locked single-writer, atomic state.json via tmp+rename)
  - TmuxSpawn (session/window creation, env injection)
  - Supervisor (Run loop: flock → tmux window → plugin → signal forwarding → cleanup)
  - Plugin interface (PluginEnv with UpdateService, Bus, Tmux, Target)
  - EventBus (in-memory pub/sub, cached last-state for new subscribers)
  - EventSocket (unix domain socket SSE server)
  - Poll and TailFile utilities
  - tests
- [x] implement devport run (Part 2)
  - TOML spec parser for devport.local.toml
  - Port allocation (find free ports, bind to claim)
  - DevportPlugin (health checks, reports port/state/health)
  - .devport.env writer
  - CLI: `devport run <spec> --tmux-session <name> --state-dir <path>`
  - test with a simple service (e.g. python -m http.server)

## Refactor agentboss to use libs/hayeah-go/supervisor

Work in `~/github.com/hayeah/agentboss`. Replace the hand-rolled supervisor/session/store/tmux/event code with the shared `libs/hayeah-go/supervisor` library. agentboss becomes a thin consumer: ClaudePlugin + CodexPlugin implement the Plugin interface, the lease system layers on via socket control handlers.

Read the supervisor library at `~/github.com/hayeah/dotfiles/libs/hayeah-go/supervisor/` and its README. Read the current agentboss code to understand what maps to what.

**IMPORTANT**: use `--tmux-session __agent_test` (or `AGENTBOSS_TMUX_SESSION=__agent_test`) for ALL testing. Do NOT touch the `__agent` session — other agents may be running in it.

- [x] refactor
  - replace SessionStore/SessionWriter with supervisor.Store/Writer
  - replace Tmux abstraction with supervisor.Tmux
  - replace EventBus with supervisor.EventBus
  - replace socket SSE server with supervisor.EventSocket
  - convert ClaudeWatcher/CodexWatcher to Plugin interface implementations
  - supervisor.Run() replaces the hand-rolled Run() in supervisor.go
  - keep the lease system — wire it as socket control handlers on the supervisor's EventSocket
  - keep the spawner — it creates TmuxSpawn configs and calls supervisor.New()
  - all existing `go test ./...` must pass after refactor
  - test spawning with `--tmux-session __agent_test`, verify state.json format matches new schema
  - clean up `__agent_test` session after tests
- [x] review and cleanup refactored code with claude
  - codex did a large refactor — expect rough edges, dead code, inconsistencies
  - read through the full diff vs master, not just spot checks
  - verify Plugin interface implementations (ClaudePlugin, CodexPlugin) are complete and correct
  - check that lease system and socket control handlers are properly wired
  - hunt for dead code, leftover hand-rolled supervisor logic that should have been removed
  - fix naming inconsistencies, stale comments referencing old abstractions
  - ensure error handling and cleanup paths are coherent after the rewrite
- [x] thorough testing and bug fixing
  - run full `go test ./...` — expect failures, fix them
  - spawn a claude session with `--tmux-session __agent_test`, verify state.json lifecycle
  - spawn a codex session with `--tmux-session __agent_test`, verify state.json lifecycle
  - test `agentboss ls`, `agentboss state`, `agentboss wait`, `agentboss send` against live sessions
  - verify lease acquire/release works correctly through supervisor socket
  - stress the edge cases: kill mid-session, double-spawn, concurrent leases
  - fix bugs found during testing — this is a large refactor, there will be bugs
  - clean up `__agent_test` session after tests

## Update supervisor lib + devportv2: socket protocol is plugin-owned

The supervisor library at `libs/hayeah-go/supervisor/` currently bakes in EventBus and EventSocket. These should be service-specific concerns owned by the plugin, not the library.

Changes:
- **supervisor lib**: remove EventBus and EventSocket from the core. Instead, provide the unix socket `net.Listener` to the plugin via `PluginEnv`. The plugin registers its own HTTP handlers.
- **devportv2**: DevportPlugin owns its health check endpoint on rpc.sock. No EventBus dependency.
- **specs**: already updated at `$MDNOTES_ROOT/2026-04-10/go-supervisor-lib-spec.md` and `supervisor-pattern.md`.

- [x] update supervisor lib
  - remove event.go (EventBus) and socket.go (EventSocket) from the library
  - plugin creates rpc.sock directly in state dir (flock doesn't block file creation)
  - keep flock, store, writer, tmux, supervisor, poll, tailfile, atomic
  - update tests
- [x] update devportv2 devport run
  - DevportPlugin serves its own health endpoint on the socket
  - no EventBus import

## Add bydate symlinks to boss checkout

Hard to find which workspaces are actively being worked on. When `boss checkout` creates or reuses a workspace, also maintain a `bydate/` index under `$BOSS_ROOT`:

```
$BOSS_ROOT/
  bydate/
    2026-04-10/
      163512-add-user-authentication -> ../../add-user-authentication
      170045-fix-oauth-redirect -> ../../fix-oauth-redirect
```

- [x] implement and test
  - on `boss checkout` (or `boss spawn`), create `$BOSS_ROOT/bydate/<YYYY-MM-DD>/<HHMMSS_ms>-<slug>` symlink pointing back at the workspace
  - skip if a symlink for the same slug already exists under today's date dir
  - `boss ls` could optionally show the creation timestamp from the bydate link

## Update agent loop to create devport.local.yaml for dev servers

Agents should automatically manage per-worktree dev services via `devport run`. See spec: `$MDNOTES_ROOT/2026-04-10/dev-services-spec.md`.

Convention: `devport run devport.local.yaml` uses `devport.local.env` as the env output file (matching the yaml name, so different scopes get different env files).

Also address stale Vite friction: agents keep getting burned by leftover dev servers from previous sessions. With devport run, lifetime is tied to the agent process — no stale servers.

- [x] implement
  - update AGENT_LOOP.md: if the repo has `devport.local.toml`, run `devport run devport.local.toml` in bg after checkout, source `devport.local.env`
  - `devport run devport.local.toml` writes env to `devport.local.env` (derive env filename from toml filename)
  - run devport in bg so it dies with the agent session
  - look at recent devportv2 work that implemented `devport run`

## Add webview eval to SwiftUITap

Spec: $MDNOTES_ROOT/2026-04-10/swiftuitap-webview-eval-spec.md

Work in ~/github.com/hayeah/SwiftUITap.

- [x] spec: design eval protocol and webview registration API
- [x] implement per spec

## Speed up boss ls

`boss ls` feels slow. Profile and optimize. Work in `~/github.com/hayeah/dotfiles/skills/boss/`.

The likely bottleneck is `agentboss.session_for_cwd()` calling `agentboss ls` once per section, plus `workspace.diff_per_repo()` running git diff per repo per section. Consider batching the agentboss ls call (one call, match all sections) and parallelizing the git diffs.

- [x] profile and fix
  - time the current boss ls, identify bottlenecks
  - batch the agentboss ls call instead of per-section
  - parallelize git diff calls across sections
  - measure improvement
- [x] skip git diff for done workspaces
  - done sections (no pending todos, no agent) don't need diffs — just skip them
  - no caching needed, just don't run the git commands

## Structured section AST for bossdoc parser

Replace the regex-only section body parsing in `bossdoc.py` with a structured AST. Each section body gets parsed into typed items with line numbers.

Work in `~/github.com/hayeah/dotfiles/skills/boss/`.

```python
@dataclass
class Checkbox:
    checked: bool
    text: str
    nested: list[str]     # plain bullet lines under this checkbox
    line: int             # line number in BOSS.md

@dataclass
class Prose:
    text: str
    line: int

@dataclass  
class Section:
    header: str
    slug: str
    header_line: int
    items: list[Checkbox | Prose]
```

- [ ] implement and benchmark
  - parse section body into Checkbox and Prose items with line numbers
  - rewrite has_pending, is_spec_only, find_nested_checkboxes to use the AST
  - write a micro benchmark (parse BOSS.md 1000x, report median)
  - golf it — keep it fast, even if it's probably fast enough already
  - existing tests must pass
