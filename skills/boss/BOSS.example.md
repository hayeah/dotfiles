# Example Boss Doc

This is a sample boss doc. Copy it to your project as `BOSS.md` and write your own sections. No frontmatter, no inline metadata — the doc is just headers and todos.

Top-level `##` sections are features. Each gets a feature workspace at `$BOSS_ROOT/<slug>/` and a subagent. **Keep top-level checkboxes coarse** — usually one or two `- [ ]` per section. Nested bullets under a checkbox are instructions/breakdown for the agent, not separate todos. Fine-grained step tracking belongs in the agent's worklog `## Todos`, not the boss doc.

A section is **done** when every top-level `- [ ]` in its body is ticked. There is no `[x]` prefix on the section header. Section headers must be unique by slug. The slug is derived as `lowercase + non-alphanumerics → -`.

## Add user authentication

Chunky feature touching a lot of files. The agent will write a spec at `$BOSS_ROOT/add-user-authentication/specs/main.md` on first turn and seed its own todo list in the workspace worklog.

- [ ] design schema and write the spec
  - read existing user/auth code (if any) before writing the spec
  - prefer UUIDs over auto-increment ints for user/session IDs
- [ ] implement and verify
  - cover happy path + bad password + missing user in tests
  - dogfood with the signup flow

## Wire up password reset email

Edit in the main checkout (no worktree — small change, just one new endpoint). Spawn this with `boss spawn wire-up-password-reset-email --mode main-repo`.

- [ ] implement and verify
  - send via the resend skill
  - add a reset token table + endpoint

## Refactor config loader

Small enough that all the boxes ship together. The workspace stays around as frozen history once the boxes are ticked.

- [x] extract config parsing + add a malformed-input test

---

After spawning, the on-disk layout under `$BOSS_ROOT/` looks like:

```
$BOSS_ROOT/
  friction.md
  add-user-authentication/
    WORKLOG.md
    specs/main.md
    repos/github.com/hayeah/myapp -> ~/github.com/hayeah/myapp/.worktrees/add-user-authentication
    tmp/143052_283-signup-flow.png
  wire-up-password-reset-email/
    WORKLOG.md
    repos/github.com/hayeah/myapp -> ~/github.com/hayeah/myapp     # main-repo mode
  refactor-config-loader/
    WORKLOG.md
    repos/github.com/hayeah/myapp -> ~/github.com/hayeah/myapp/.worktrees/refactor-config-loader
```

The slug is the join key between the BOSS.md section, the workspace dir, and the agentboss session (whose cwd is the workspace root). `boss ls` performs the join on demand — there is no `meta.json` ledger.
