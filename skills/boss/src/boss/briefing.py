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
Section header: {header}
Section slug:   {slug}
Boss doc:       {boss_doc}

Your cwd is the workspace root, NOT a repo. Your first job is to:

  1. Read the boss doc and locate your section by slug.
  2. Decide which repo(s) you need to touch.
  3. For each repo, create a worktree at <repo>/.worktrees/{slug} on a
     new branch named {slug} from master, run the .worktrees.setup hook
     if present, and symlink it under repos/<host>/<user>/<name> in the
     workspace. Example for ~/github.com/hayeah/myapp:

       REPO=~/github.com/hayeah/myapp
       git -C "$REPO" worktree add ".worktrees/{slug}" -b "{slug}" master
       [ -x "$REPO/.worktrees.setup" ] && \\
         ( cd "$REPO/.worktrees/{slug}" && "$REPO/.worktrees.setup" )
       mkdir -p repos/github.com/hayeah
       ln -s "$REPO/.worktrees/{slug}" repos/github.com/hayeah/myapp

  4. Read existing WORKLOG.md (it has been minted from the template).
     For non-trivial work, write a spec at specs/main.md and link it
     from WORKLOG.md frontmatter `spec:`.
  5. Seed your `## Todos` list and start working.

If you discover additional repos mid-task, add more symlinks the same
way — no coordination with the boss required. Begin.
"""


MAIN_REPO_BRIEFING = """\
You are a boss subagent. Read {agent_loop_path} for your full instructions.

You are running in MAIN-REPO mode (the section says edit-in-place / no worktree).

Your workspace: {workspace}
Your worklog:   {worklog}
Section header: {header}
Section slug:   {slug}
Boss doc:       {boss_doc}

Your cwd is the workspace root, NOT a repo. Your first job is to:

  1. Read the boss doc and locate your section by slug.
  2. Decide which repo to edit. Symlink it directly under repos/<host>/<user>/<name>:

       mkdir -p repos/github.com/hayeah
       ln -s ~/github.com/hayeah/myapp repos/github.com/hayeah/myapp

  3. Read existing WORKLOG.md and (for non-trivial work) write specs/main.md.
  4. Seed your `## Todos` list and start working.

MAIN-REPO discipline: the working tree is shared with the human's in-flight
work. NEVER `git add -A` or `git add .`. Always stage explicit paths and
only the files your section actually touched. Begin.
"""


def render(slug: str, header: str, mode: str, boss_doc: Path) -> str:
    lay = workspace.layout(slug)
    template = WORKTREE_BRIEFING if mode == "worktree" else MAIN_REPO_BRIEFING
    return template.format(
        agent_loop_path=AGENT_LOOP_PATH,
        workspace=lay.root,
        worklog=lay.worklog,
        header=header,
        slug=slug,
        boss_doc=boss_doc,
    )
