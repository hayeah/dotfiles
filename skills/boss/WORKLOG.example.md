<!--
This file lives at:
  $BOSS_ROOT/add-user-authentication/WORKLOG.md

Sibling files in the same workspace:
  $BOSS_ROOT/add-user-authentication/
    WORKLOG.md
    specs/
      main.md                       # primary spec, written by the agent on first turn
      schema-alternatives.md        # ad-hoc supporting design notes (optional)
    repos/
      github.com/hayeah/myapp -> ~/github.com/hayeah/myapp/.worktrees/add-user-authentication
    tmp/
      143052_283-signup-flow.png    # screenshots, transcripts, scratch scripts
      143205_117-schema-dump.sql
-->
---
status: working          # working | blocked | done
section: Add user authentication
slug: add-user-authentication
mode: worktree           # worktree | main-repo
spec: specs/main.md
created: 2026-04-11T07:30:16Z
---

> ## Add user authentication
>
> Work in ~/github.com/hayeah/myapp.
>
> - [ ] implement per spec
>   - schema + endpoint + tests
<!-- Blockquote above is a mirror of the current BOSS.md section text.
     `boss spawn` writes and refreshes this on every spawn/respawn —
     don't edit it by hand. -->

## Todos
<!-- Finer-grained than the boss-doc top-level checkboxes. Tick off as you go.
     The boss-doc top-level checkboxes are user-facing milestones;
     this list is your internal driver. Add new items as you discover them.
     For multi-stage work, use `### phase label` sub-headings. -->

- [x] design users + sessions schema (UUIDs per the section's nested note)
- [x] write the migration
- [x] add a unit test for the schema
- [x] wire up POST /signup
- [x] add test for /signup happy path
- [ ] generate session tokens (HMAC over user_id + iat + nonce)
- [ ] wire up POST /login
- [ ] add test for /login happy path
- [ ] add tests for bad password + missing user
- [ ] confirm session cookie is HttpOnly + Secure (per boss notes)
- [ ] tick off the two boss-doc checkboxes once implementation is in

### Blocked
- (none)

## Agent log
<!-- Prefer `boss agent log <slug> "<message>"` — it appends a timestamped
     entry here for you. Questions for the boss live here too; the boss
     watches this section and replies via `boss nudge`. -->
- 2026-04-11T14:01Z read section + spec, starting on schema design
- 2026-04-11T14:05Z wrote migration for users + sessions tables, used UUIDs per the spec
- 2026-04-11T14:08Z ran `pytest tests/test_schema.py` — passes
- 2026-04-11T14:12Z wired up signup endpoint
- 2026-04-11T14:15Z hit a quirk: the test client fixture didn't auto-create the sessions table; had to add it to conftest.py  #friction
- 2026-04-11T14:22Z signup endpoint test passes (POST /signup → 201 + user row)
- 2026-04-11T14:30Z starting on /login

## Boss log
<!-- The boss appends timestamped lines here via `boss nudge`. Re-read on every turn. -->
- 2026-04-11T14:18Z the schema should use UUIDs not ints — confirmed, already done
- 2026-04-11T14:32Z for /login add a test that asserts the session cookie is HttpOnly + Secure

## Evidence
<!--
Filled in only when status: done. Boss will not lgtm without this.
Example shape (replace with real evidence for your section):

### Backend tests

```
$ pytest tests/test_auth.py -v
tests/test_auth.py::test_signup_creates_user PASSED
tests/test_auth.py::test_login_returns_session_cookie PASSED
tests/test_auth.py::test_login_rejects_bad_password PASSED
tests/test_auth.py::test_login_rejects_unknown_user PASSED
4 passed in 0.42s
```

Tests live at `tests/test_auth.py`. They hit the real endpoints via FastAPI's TestClient (no mocks of the DB layer).

### Manual repro

```
$ curl -i -X POST localhost:8000/signup -d '{"email":"a@b.co","password":"hunter2"}' -H 'content-type: application/json'
HTTP/1.1 201 Created
...

$ curl -i -X POST localhost:8000/login -d '{"email":"a@b.co","password":"hunter2"}' -H 'content-type: application/json'
HTTP/1.1 200 OK
set-cookie: session=abc123...; HttpOnly; Secure; Path=/
```

Full transcript saved at `tmp/150421_004-signup-login-transcript.txt`.

### Screenshot

![signup flow](tmp/143052_283-signup-flow.png)
-->

## Trouble report
<!--
ROLLING — update every time you tick a todo, not just at the end. The commit log
already says what was built — this section is for what the commit log won't tell you.

- **Friction**: tooling rough edges, missing harnesses, things that wasted time
- **Bugs found along the way**: not necessarily fixed in this section — note them so the boss can spawn follow-up sections
- **Detours**: paths I tried that didn't work, and why, so the next agent doesn't repeat them
- **Kludges**: "fixed for now" hacks that need a real fix later. Be explicit: WHERE the kludge is, WHY it's a kludge, and WHAT a real fix would look like
- **Surprises**: things about the codebase or libraries that weren't what I expected

Example:

- kludge: hardcoded the JWT secret in `auth/jwt.py:14` because there's no config loader for secrets yet. real fix: wire it through whatever config system the rest of the app uses.
- detour: tried using `passlib` for password hashing first, but it pulled in a deprecated `bcrypt` API and threw warnings. switched to plain `bcrypt`.
- bug: noticed that `/health` returns 500 if the DB is unreachable instead of a structured error. unrelated to this section but worth a follow-up.
- friction: the test fixture didn't auto-create the sessions table. had to patch conftest.py. the project's test scaffolding could use a once-per-session migration helper.  #friction
-->
