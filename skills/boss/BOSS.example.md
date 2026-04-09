# Example Boss Doc

This is a sample boss doc. Copy it to your project as `BOSS.md` and write your own sections. No frontmatter, no inline metadata — the doc is just headers and todos.

Top-level `##` sections are features. Each gets a per-repo worktree at `<repo>/.worktrees/<slug>` and a subagent. **Keep top-level checkboxes coarse** — usually one `- [ ]` per section, occasionally two or three for genuinely distinct phases. Nested bullets under a checkbox are instructions/breakdown for the agent, not separate todos. Fine-grained step tracking belongs in the agent's worklog `## Todos`, not the boss doc. When the boss lgtm's a section, the header gets prefixed with `[x]`.

All per-section state lives in `$MDNOTES_ROOT/boss/meta.json`, keyed by section slug. Section headers must be unique by slug. The meta entries are minimal — `header`, `worklog` (path to the notes dir), `session` (agentboss key) — everything else is derivable.

## Add user authentication

Chunky feature touching a lot of files. The agent will write a spec on first turn and seed its own todo list in the worklog.

- [ ] implement and verify
  - read the existing auth code (if any) before writing the spec
  - prefer UUIDs over auto-increment ints for user/session IDs
  - cover happy path + bad password + missing user in tests

## Wire up password reset email

Edit in the main checkout (no worktree — small change, just one new endpoint).

- [ ] implement and verify
  - send via the resend skill
  - add a reset token table + endpoint

## [x] Refactor config loader

- [x] extract config parsing + add a malformed-input test

---

Corresponding `$MDNOTES_ROOT/boss/meta.json` after the boss has spawned subagents for the open sections and closed the refactor:

```json
{
  "add-user-authentication": {
    "header": "Add user authentication",
    "worklog": "2026-04-08/143052_283-add-user-authentication",
    "session": "boss-a3f"
  },
  "wire-up-password-reset-email": {
    "header": "Wire up password reset email",
    "worklog": "2026-04-08/144130_871-wire-up-password-reset-email",
    "session": "boss-c14"
  },
  "refactor-config-loader": {
    "header": "Refactor config loader",
    "worklog": "2026-04-08/091200_450-refactor-config-loader",
    "session": null
  }
}
```

The closed section's `session` is `null` (the agentboss session was killed on close), but the entry stays in `meta.json` so the worklog dir at `2026-04-08/091200_450-refactor-config-loader/` remains discoverable as history.

The worktree for an open section is always at `<repo>/.worktrees/<slug>` and its branch is also `<slug>`. No lookup needed.
