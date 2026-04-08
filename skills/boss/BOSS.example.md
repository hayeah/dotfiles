# Example Boss Doc

This is a sample boss doc. Copy it to your project as `BOSS.md` and write your own sections. No frontmatter, no inline metadata — the doc is just headers and todos.

Top-level `##` sections are features. Each gets a worktree and a subagent. Top-level `- [ ]` checkboxes are todos the boss tracks. Nested bullets are notes — do not mark them. When the human lgtms a section, the header gets prefixed with `[x]`.

All per-section state (worktree, agentboss session key, section dir) lives in `$MDNOTES_ROOT/boss/meta.json`, keyed by section slug. Section headers must be unique by slug.

## Add user authentication

- [ ] design user + session schema
  - prefer UUIDs over auto-increment ints
  - sessions table needs an index on token
- [ ] implement signup + login endpoints
- [ ] add integration tests
  - cover the happy path
  - cover bad password, missing user

## Wire up password reset email

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
    "dir": "2026-04-08/143052.283-add-user-authentication",
    "worktree": ".worktrees/001",
    "session": "boss-a3f",
    "spawned_at": "2026-04-08T14:30:52.283Z"
  },
  "wire-up-password-reset-email": {
    "header": "Wire up password reset email",
    "dir": "2026-04-08/144130.871-wire-up-password-reset-email",
    "worktree": ".worktrees/002",
    "session": "boss-c14",
    "spawned_at": "2026-04-08T14:41:30.871Z"
  },
  "refactor-config-loader": {
    "header": "Refactor config loader",
    "dir": "2026-04-08/091200.450-refactor-config-loader",
    "worktree": ".worktrees/003",
    "session": null,
    "spawned_at": "2026-04-08T09:12:00.450Z"
  }
}
```

Note that the closed section's `session` is `null` (the agentboss session is gone after `lgtm`), but the entry stays in `meta.json` so the section dir at `2026-04-08/091200.450-refactor-config-loader/` remains discoverable as history.
