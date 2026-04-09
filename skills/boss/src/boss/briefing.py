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

BRIEFING = """\
You are a boss subagent. Read {agent_loop_path} for your full instructions.

Mode: {mode}
Workspace: {workspace}
Worklog:   {worklog}
Section:   {header}

Your cwd is the workspace root, NOT a repo. The boss has handed you the
section text below. **You do not know where the boss doc lives and you
must not look for it or modify it.** The boss owns the boss doc; you own
WORKLOG.md and your repos. If a top-level checkbox needs ticking, the
boss will tick it after reviewing your evidence and merging.

----- SECTION TEXT -----
{section_body}
----- END SECTION TEXT -----

Your first job is to:

  1. Read the section text above and decide which repo(s) you need.
  2. For each repo, run:

       boss checkout ~/github.com/<user>/<repo>

     This creates a worktree (or symlinks directly in main-repo mode),
     runs any setup hooks (.worktrees.setup / pymake worktree_setup),
     and wires the symlink into repos/. If you discover additional
     repos mid-task, just `boss checkout` them — no coordination
     with the boss required.{main_repo_note}
  3. Read existing WORKLOG.md (minted from the template by boss spawn).
     For non-trivial work, write a spec at specs/main.md.
  4. Seed your `## Todos` list and start working.

Begin.
"""

MAIN_REPO_NOTE = """

     MAIN-REPO discipline: the working tree is shared with the human's
     in-flight work. NEVER `git add -A` or `git add .`. Always stage
     explicit paths and only the files your section actually touched."""


def render(slug: str, header: str, section_body: str, mode: str) -> str:
    lay = workspace.layout(slug)
    return BRIEFING.format(
        agent_loop_path=AGENT_LOOP_PATH,
        workspace=lay.root,
        worklog=lay.worklog,
        header=header,
        mode=mode.upper(),
        section_body=section_body.strip(),
        main_repo_note=MAIN_REPO_NOTE if mode == "main-repo" else "",
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
to `status: working` and seed new todos. If you need new repos, use
`boss checkout ~/github.com/<user>/<repo>` — it won't re-create
worktrees that already exist.

----- SECTION TEXT -----
{section_body}
----- END SECTION TEXT -----

Reminder: you do not know where the boss doc lives, do not look for it,
and do not modify it. Continue from where you left off.
"""


def render_resume(slug: str, header: str, section_body: str) -> str:
    lay = workspace.layout(slug)
    return RESUME_BRIEFING.format(
        workspace=lay.root,
        worklog=lay.worklog,
        header=header,
        section_body=section_body.strip(),
    )
