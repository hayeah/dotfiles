# Example Boss Doc

This is a sample boss doc. Copy it to your project as `BOSS.md` and write your own sections. No frontmatter, no inline metadata — the doc is just headers and todos.

Top-level `##` sections are features. Each gets a worktree and a subagent. Top-level `- [ ]` checkboxes are todos the boss tracks. Nested bullets are notes — do not mark them. When the human lgtms a section, the header gets prefixed with `[x]`.

All per-section state lives in `$MDNOTES_ROOT/boss/meta.json`, keyed by section slug. Section headers must be unique by slug. The meta entries are minimal — `header`, `worklog` (path to the notes dir), `session` (agentboss key) — everything else is derivable from agentboss + git-worktree.

## Add user authentication

This is a chunky feature that touches a lot of files — please use a worktree off origin/master so it's isolated from other in-flight work.

- [ ] design user + session schema
  - prefer UUIDs over auto-increment ints
  - sessions table needs an index on token
- [ ] implement signup + login endpoints
- [ ] add integration tests
  - cover the happy path
  - cover bad password, missing user

## Wire up password reset email

(No worktree needed — small change, run in the main checkout.)

- [ ] add reset token table
- [ ] send email via Resend (see resend skill)
- [ ] add reset endpoint

## [x] Refactor config loader

- [x] extract config parsing into its own module
- [x] update all call sites
- [x] add a unit test for malformed input

---

Corresponding `$MDNOTES_ROOT/boss/meta.json` after the boss has spawned subagents for the open sections and closed the refactor:

```json
{
  "add-user-authentication": {
    "header": "Add user authentication",
    "worklog": "2026-04-08/143052.283-add-user-authentication",
    "session": "boss-a3f"
  },
  "wire-up-password-reset-email": {
    "header": "Wire up password reset email",
    "worklog": "2026-04-08/144130.871-wire-up-password-reset-email",
    "session": "boss-c14"
  },
  "refactor-config-loader": {
    "header": "Refactor config loader",
    "worklog": "2026-04-08/091200.450-refactor-config-loader",
    "session": null
  }
}
```

The closed section's `session` is `null` (the agentboss session is gone after `lgtm`), but the entry stays in `meta.json` so the worklog dir at `2026-04-08/091200.450-refactor-config-loader/` remains discoverable as history.

To find the worktree for an open section, query `git-worktree list --json` for the entry whose branch matches the slug — the branch name and the slug are the same by convention.
