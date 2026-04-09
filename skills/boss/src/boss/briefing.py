"""AGENT_LOOP briefing template.

The briefing is constructed by `boss spawn` and sent to the freshly spawned
agent via `agentboss send`. Templated (not caller-supplied prose) so the
text stays in sync with AGENT_LOOP.md and can't be typo'd from the calling
side.
"""

from __future__ import annotations

from pathlib import Path

from . import workspace


AGENT_LOOP_PATH = "~/github.com/hayeah/dotfiles/skills/boss/AGENT_LOOP.md"

WORKTREE_BRIEFING = """\
You are a boss subagent. Read {agent_loop_path} for your full instructions.

You are running in WORKTREE mode.

Your workspace: {workspace}
Your worklog:   {worklog}
Section title:  {header}

Your cwd is the workspace root, NOT a repo. The boss has handed you the
section text below. **You do not know where the boss doc lives and you
must not look for it or modify it.** The boss owns the boss doc; you own
WORKLOG.md and your worktrees. If a top-level checkbox needs ticking,
the boss will tick it after reviewing your evidence and merging.

----- SECTION TEXT -----
{section_body}
----- END SECTION TEXT -----

Your first job is to:

  1. Read the section text above and decide which repo(s) you need to touch.
  2. For each repo, create a worktree at <repo>/.worktrees/{slug} on a
     new branch named {slug} from master, run the .worktrees.setup hook
     if present, and symlink it under repos/<host>/<user>/<name> in the
     workspace. Example for ~/github.com/hayeah/myapp:

       REPO=~/github.com/hayeah/myapp
       git -C "$REPO" worktree add ".worktrees/{slug}" -b "{slug}" master
       [ -x "$REPO/.worktrees.setup" ] && \\
         ( cd "$REPO/.worktrees/{slug}" && "$REPO/.worktrees.setup" )
       mkdir -p repos/github.com/hayeah
       ln -s "$REPO/.worktrees/{slug}" repos/github.com/hayeah/myapp

  3. Read existing WORKLOG.md (it has been minted from the template).
     For non-trivial work, write a spec at specs/main.md and link it
     from WORKLOG.md frontmatter `spec:`.
  4. Seed your `## Todos` list (this is YOUR fine-grained driver — separate
     from the boss-doc top-level boxes which you never touch) and start
     working.

If you discover additional repos mid-task, add more symlinks the same
way — no coordination with the boss required. Begin.
"""


MAIN_REPO_BRIEFING = """\
You are a boss subagent. Read {agent_loop_path} for your full instructions.

You are running in MAIN-REPO mode (the section says edit-in-place / no worktree).

Your workspace: {workspace}
Your worklog:   {worklog}
Section title:  {header}

Your cwd is the workspace root, NOT a repo. The boss has handed you the
section text below. **You do not know where the boss doc lives and you
must not look for it or modify it.** The boss owns the boss doc; you own
WORKLOG.md and the files you edit in main-repo mode. If a top-level
checkbox needs ticking, the boss will tick it after reviewing your
evidence.

----- SECTION TEXT -----
{section_body}
----- END SECTION TEXT -----

Your first job is to:

  1. Read the section text above and decide which repo to edit. Symlink it
     directly under repos/<host>/<user>/<name>:

       mkdir -p repos/github.com/hayeah
       ln -s ~/github.com/hayeah/myapp repos/github.com/hayeah/myapp

  2. Read existing WORKLOG.md and (for non-trivial work) write specs/main.md.
  3. Seed your `## Todos` list and start working.

MAIN-REPO discipline: the working tree is shared with the human's in-flight
work. NEVER `git add -A` or `git add .`. Always stage explicit paths and
only the files your section actually touched. Begin.
"""


def render(slug: str, header: str, section_body: str, mode: str) -> str:
    lay = workspace.layout(slug)
    template = WORKTREE_BRIEFING if mode == "worktree" else MAIN_REPO_BRIEFING
    return template.format(
        agent_loop_path=AGENT_LOOP_PATH,
        workspace=lay.root,
        worklog=lay.worklog,
        header=header,
        slug=slug,
        section_body=section_body.strip(),
    )


RESUME_BRIEFING = """\
Boss is re-engaging — `boss spawn` hit your existing live session.

Workspace: {workspace}
Worklog:   {worklog}
Section:   {header}

The boss has handed you the latest section text below. The section may
have new top-level checkboxes since you last looked. Re-read your
WORKLOG.md, then compare the section text below against your todos.

If `status: done` and there is new work in the section text, flip back
to `status: working` and seed new todos.

----- SECTION TEXT -----
{section_body}
----- END SECTION TEXT -----

Reminder: you do not know where the boss doc lives, do not look for it,
and do not modify it. Continue from where you left off. Do not re-create
worktrees that already exist under repos/.
"""


def render_resume(slug: str, header: str, section_body: str) -> str:
    lay = workspace.layout(slug)
    return RESUME_BRIEFING.format(
        workspace=lay.root,
        worklog=lay.worklog,
        header=header,
        section_body=section_body.strip(),
    )
