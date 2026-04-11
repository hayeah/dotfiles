"""Typer entry point for the `boss` CLI."""

from __future__ import annotations

import json
import sys
from datetime import date as date_type
from pathlib import Path

import typer

from . import (
    agentboss,
    briefing,
    bossdoc,
    doctor as doctor_mod,
    lgtm as lgtm_mod,
    ls as ls_mod,
    pool,
    sim,
    worklog as worklog_mod,
    workspace,
)
from .util import sh

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Workflow CLI for the boss skill — workspaces, BOSS.md ↔ agentboss join, lgtm gating.",
)


def _resolve_boss_doc(path: Path | None) -> Path:
    if path is None:
        path = Path("BOSS.md")
    return path.resolve()


AGENT_PRESETS = {
    "claude": {
        "cmd": ["claude", "--dangerously-skip-permissions"],
        "detector": "claude",
    },
    "codex": {
        "cmd": ["bunx", "--bun", "@openai/codex", "--dangerously-bypass-approvals-and-sandbox"],
        "detector": "codex",
    },
}


@app.command()
def spawn(
    section: str = typer.Argument(..., help="Slug or unique substring of a section header."),
    mode: str = typer.Option("worktree", "--mode", help="worktree | main-repo"),
    agent: str = typer.Option("claude", "--agent", help="Agent to spawn: claude | codex"),
    boss_doc: Path = typer.Option(Path("BOSS.md"), "--boss-doc", help="Path to BOSS.md."),
    claude_args: list[str] = typer.Option(
        None,
        "--claude-arg",
        help="Extra arg to pass to the agent command (repeatable).",
    ),
) -> None:
    """Set up a workspace for a section and spawn an agent inside it."""
    if mode not in ("worktree", "main-repo"):
        typer.echo(f"error: invalid --mode {mode!r} (use 'worktree' or 'main-repo')", err=True)
        raise typer.Exit(2)

    if agent not in AGENT_PRESETS:
        typer.echo(f"error: unknown --agent {agent!r} (use {', '.join(AGENT_PRESETS)})", err=True)
        raise typer.Exit(2)

    doc = _resolve_boss_doc(boss_doc)
    try:
        sections = bossdoc.load(doc)
    except bossdoc.BossDocError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1)

    matches = [s for s in sections if section == s.slug]
    if not matches:
        matches = [s for s in sections if section in s.slug or section.lower() in s.header.lower()]
    if not matches:
        typer.echo(f"error: no section matching {section!r}", err=True)
        raise typer.Exit(1)
    if len(matches) > 1:
        typer.echo(
            f"error: {section!r} is ambiguous: " + ", ".join(m.slug for m in matches),
            err=True,
        )
        raise typer.Exit(1)
    s = matches[0]

    lay = workspace.layout(s.slug)

    # Idempotent spawn: if a live session already owns this workspace,
    # re-engage it instead of refusing.
    live = None
    if lay.root.is_dir():
        live = agentboss.session_for_cwd(lay.root)

    if live is not None:
        key = live.get("id") or "?"
        # Refresh the BOSS.md section mirror blockquote before the agent re-reads.
        if lay.worklog.exists():
            workspace.set_section_quote(lay.worklog, s.body, s.header)
        resume_msg = briefing.render_resume(
            slug=s.slug, header=s.header, section_body=s.body
        )
        try:
            agentboss.submit(key, resume_msg)
        except agentboss.AgentbossError as e:
            typer.echo(
                f"warning: re-engaged existing session {key} but resume briefing failed: {e}",
                err=True,
            )
        typer.echo(f"re-engaged: slug={s.slug} key={key} workspace={lay.root}")
        return

    workspace.create(s.slug, s.header, mode)
    workspace.set_section_quote(lay.worklog, s.body, s.header)

    preset = AGENT_PRESETS[agent]
    cmd = list(preset["cmd"])
    if claude_args:
        cmd.extend(claude_args)

    try:
        descriptor = agentboss.run(cwd=lay.root, command=cmd, detector=preset["detector"])
    except agentboss.AgentbossError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1)

    key = descriptor.get("id") or "?"

    # Persist agent_id so `boss checkout` can write it into lease files.
    workspace.update_boss_json(lay.root, updates={"agent_id": key})

    msg = briefing.render(
        slug=s.slug, header=s.header, section_body=s.body, mode=mode
    )
    try:
        agentboss.send(key, msg)
    except agentboss.AgentbossError as e:
        typer.echo(f"warning: spawned agent {key} but briefing submit failed: {e}", err=True)

    typer.echo(f"spawned: slug={s.slug} key={key} workspace={lay.root}")


@app.command()
def add(
    boss_doc: Path = typer.Option(Path("BOSS.md"), "--boss-doc", help="Path to BOSS.md."),
    date: str = typer.Option("", "--date", help="Date group (YYYY-MM-DD). Defaults to today."),
) -> None:
    """Append a new section to the boss doc (read from stdin).

    The section text must contain a `## Header` line and typically one or
    more `- [ ]` checkboxes.  It is appended under a `# YYYY-MM-DD` date
    group, creating one if it doesn't exist yet.

    Example::

        boss add <<'EOF'
        ## Add user authentication

        - [ ] design schema and write the spec
        - [ ] implement and verify
        EOF
    """
    if not date:
        date = date_type.today().isoformat()

    section_text = sys.stdin.read()
    if not section_text.strip():
        typer.echo("error: no section text on stdin", err=True)
        raise typer.Exit(2)

    doc = _resolve_boss_doc(boss_doc)
    try:
        slug = bossdoc.append_section(doc, section_text, date)
    except bossdoc.BossDocError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1)

    typer.echo(f"added: {slug} (date group: {date})")


@app.command()
def checkout(
    repo: Path = typer.Argument(..., help="Path to the repo (e.g. ~/github.com/hayeah/myapp)."),
    no_tree: bool = typer.Option(
        False,
        "--no-tree",
        help="Main-repo mode: symlink the repo directly instead of creating a worktree.",
    ),
    ios_simulator: bool = typer.Option(
        False,
        "--ios-simulator",
        help="Lease and boot a dedicated iOS simulator for this workspace.",
    ),
) -> None:
    """Check out a repo into the current workspace's repos/ tree.

    Meant to be called by the agent from inside a workspace. Reads
    `.boss.json` (written by `boss spawn`) to discover the slug, mode,
    and agent_id.

    In worktree mode (default): leases a numbered pool slot at
    <repo>/.worktrees/NNN via `agentboss lease`, reuses an existing
    slot already held by this workspace when possible, otherwise finds
    a free slot or grows the pool, resets to master, checks out a
    branch, and symlinks into repos/.

    With --ios-simulator: leases and boots a dedicated simulator UDID,
    stores it in `.boss.json`, and prints the corresponding
    `SWIFTUI_TAP_UDID` export.

    With --no-tree: symlinks the repo directly (main-repo mode).
    """
    ws_result = workspace.find_workspace()
    if ws_result is None:
        typer.echo(
            "error: not inside a boss workspace (no .boss.json found walking up from cwd)",
            err=True,
        )
        raise typer.Exit(1)

    ws_root, boss_json = ws_result
    slug = boss_json.get("slug", "")
    if not slug:
        typer.echo("error: .boss.json has no slug field", err=True)
        raise typer.Exit(1)

    agent_id = boss_json.get("agent_id", "")

    mode = "main-repo" if no_tree else boss_json.get("mode", "worktree")
    if mode == "main-repo":
        no_tree = True
    elif not agent_id:
        typer.echo("error: .boss.json has no agent_id for worktree leasing", err=True)
        raise typer.Exit(1)

    repo_path = repo.expanduser().resolve()
    if not repo_path.is_dir():
        typer.echo(f"error: repo not found at {repo_path}", err=True)
        raise typer.Exit(1)

    # Derive the symlink label from the repo path: github.com/user/name
    parts = repo_path.parts
    try:
        gh_idx = parts.index("github.com")
        label = "/".join(parts[gh_idx : gh_idx + 3])
    except (ValueError, IndexError):
        label = repo_path.name

    repos_dir = ws_root / "repos"
    link_parent = repos_dir / Path(label).parent
    link_path = repos_dir / label

    if link_path.exists() or link_path.is_symlink():
        import os
        typer.echo(f"already checked out: {label} -> {os.readlink(link_path)}")
    elif no_tree:
        link_parent.mkdir(parents=True, exist_ok=True)
        link_path.symlink_to(repo_path)
        typer.echo(f"linked (main-repo): {label} -> {repo_path}")
    else:
        # --- Pool/lease worktree mode ---
        try:
            existing = pool.find_slot_by_slug(repo_path, slug, agent_id)
            if existing is not None:
                typer.echo(f"reusing existing lease: slot {existing.name} for {slug}")
                link_parent.mkdir(parents=True, exist_ok=True)
                link_path.symlink_to(existing)
                typer.echo(f"checked out: {label} -> {existing}")
            else:
                slot = pool.find_free_slot(repo_path)
                if slot is not None:
                    typer.echo(f"leasing free slot {slot.name}")
                else:
                    slot = pool.grow_pool(repo_path)
                    typer.echo(f"created new pool slot {slot.name}")

                pool.lease_slot(slot, slug, agent_id)

                link_parent.mkdir(parents=True, exist_ok=True)
                link_path.symlink_to(slot)
                typer.echo(f"checked out: {label} -> {slot}")
        except pool.PoolError as e:
            typer.echo(f"error: {e}", err=True)
            raise typer.Exit(1)

    workspace.ensure_bydate_link(slug)

    if ios_simulator:
        if not agent_id:
            typer.echo("error: .boss.json has no agent_id for simulator leasing", err=True)
            raise typer.Exit(1)
        preferred_udid = boss_json.get("ios_simulator_udid")
        try:
            udid = sim.ensure_simulator(agent_id, preferred_udid=preferred_udid)
        except sim.SimulatorError as e:
            typer.echo(f"error: failed to lease simulator: {e}", err=True)
            raise typer.Exit(1)

        workspace.update_boss_json(
            ws_root,
            updates={
                "ios_simulator_udid": udid,
                "env": {"SWIFTUI_TAP_UDID": udid},
            },
        )
        typer.echo(f"ios simulator: {udid}")
        typer.echo(f"export SWIFTUI_TAP_UDID={udid}")


@app.command(name="ls")
def ls_cmd(
    boss_doc: Path = typer.Option(Path("BOSS.md"), "--boss-doc"),
    json_out: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
    show_all: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Include sections with no pending todos (done + parked-but-alive sessions). "
        "Default hides them so the table only shows actionable work.",
    ),
) -> None:
    """Wide read: BOSS.md ↔ workspace ↔ agentboss join.

    By default only sections with at least one unticked top-level checkbox
    are listed (the dispatch-able + running buckets). Use --all to also
    see done sections and post-lgtm sessions still hanging in tmux.
    """
    doc = _resolve_boss_doc(boss_doc)
    try:
        rows = ls_mod.collect(doc)
    except bossdoc.BossDocError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1)

    if not show_all:
        rows = [r for r in rows if r.has_pending_todos]

    if json_out:
        typer.echo(json.dumps([r.to_json() for r in rows], indent=2))
        return

    if not rows:
        if show_all:
            typer.echo("(no sections in BOSS.md)")
        else:
            typer.echo("(nothing pending — try `boss ls --all` to see everything)")
        return
    typer.echo(ls_mod.format_table(rows))


@app.command()
def lgtm(
    section: str = typer.Argument(..., help="Slug or unique substring of a section header."),
    boss_doc: Path = typer.Option(Path("BOSS.md"), "--boss-doc"),
) -> None:
    """Rebase + verify + merge --no-ff each linked repo."""
    doc = _resolve_boss_doc(boss_doc)
    try:
        sections = bossdoc.load(doc)
    except bossdoc.BossDocError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1)

    matches = [s for s in sections if section == s.slug]
    if not matches:
        matches = [s for s in sections if section in s.slug or section.lower() in s.header.lower()]
    if not matches:
        typer.echo(f"error: no section matching {section!r}", err=True)
        raise typer.Exit(1)
    if len(matches) > 1:
        typer.echo(
            f"error: {section!r} is ambiguous: " + ", ".join(m.slug for m in matches),
            err=True,
        )
        raise typer.Exit(1)
    s = matches[0]

    try:
        results = lgtm_mod.lgtm(s.slug)
    except lgtm_mod.LgtmError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1)

    all_ok = True
    for r in results:
        marker = "OK" if r.ok else "FAIL"
        typer.echo(f"{marker}  {r.label}: {r.message}")
        if not r.ok:
            all_ok = False

    # Kill the agent session after a successful merge.
    if all_ok:
        lay = workspace.layout(s.slug)
        bj = workspace.read_boss_json(lay.root)
        agent_id = bj.get("agent_id", "")
        if agent_id:
            try:
                agentboss.kill(agent_id)
                typer.echo(f"killed agent {agent_id}")
            except agentboss.AgentbossError:
                typer.echo(f"agent {agent_id} already dead")


def _resolve_worklog(slug_or_match: str) -> tuple[str, Path]:
    """Resolve a slug or unique substring to ``(slug, worklog_path)``.

    Preference order:
      1. Exact workspace dir under $BOSS_ROOT — fastest path, works without BOSS.md.
      2. Fuzzy match against BOSS.md section slugs/headers (if BOSS.md loads).

    Exits with error code 1 on no match or ambiguity.
    """
    direct = workspace.workspace_path(slug_or_match)
    if direct.is_dir():
        return slug_or_match, direct / "WORKLOG.md"

    try:
        sections = bossdoc.load(Path("BOSS.md").resolve())
    except bossdoc.BossDocError:
        typer.echo(
            f"error: no workspace at {direct} and BOSS.md not loadable",
            err=True,
        )
        raise typer.Exit(1)

    matches = [s for s in sections if slug_or_match == s.slug]
    if not matches:
        needle = slug_or_match.lower()
        matches = [
            s for s in sections
            if slug_or_match in s.slug or needle in s.header.lower()
        ]
    if not matches:
        typer.echo(f"error: no section matching {slug_or_match!r}", err=True)
        raise typer.Exit(1)
    if len(matches) > 1:
        typer.echo(
            f"error: {slug_or_match!r} is ambiguous: "
            + ", ".join(m.slug for m in matches),
            err=True,
        )
        raise typer.Exit(1)
    s = matches[0]
    lay = workspace.layout(s.slug)
    return s.slug, lay.worklog


@app.command()
def nudge(
    section: str = typer.Argument(..., help="Slug or unique substring."),
    message: str = typer.Argument(None, help="Note text. Omit to read from stdin."),
) -> None:
    """Append a timestamped note to ``## Boss log`` and wake the agent.

    If a message argument is omitted, reads the note from stdin — so the
    caller can heredoc a multi-line note. Then finds the live agentboss
    session for this workspace (if any) and sends a ``re-read your
    worklog`` nudge. If no live session is found, the note is still
    appended (the agent will pick it up on respawn).
    """
    slug, worklog_path = _resolve_worklog(section)

    if message is None:
        if sys.stdin.isatty():
            typer.echo(
                "error: no message given and stdin is a TTY — "
                "pass a message arg or pipe one in",
                err=True,
            )
            raise typer.Exit(2)
        message = sys.stdin.read()

    if not message.strip():
        typer.echo("error: empty message", err=True)
        raise typer.Exit(2)

    if not worklog_path.exists():
        typer.echo(f"error: worklog not found at {worklog_path}", err=True)
        raise typer.Exit(1)

    try:
        worklog_mod.append_boss_note(worklog_path, message)
    except worklog_mod.WorklogError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1)

    typer.echo(f"appended to Boss log: {slug}")

    lay = workspace.layout(slug)
    live = agentboss.session_for_cwd(lay.root)
    if live is None:
        typer.echo("no live agent session — note will be read on next spawn")
        return

    key = live.get("id") or "?"
    try:
        agentboss.send(key, "re-read your worklog — new note from boss")
    except agentboss.AgentbossError as e:
        typer.echo(f"warning: failed to send nudge to {key}: {e}", err=True)
        return
    typer.echo(f"nudged agent {key}")


agent_app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Agent-facing subcommands (call from inside an agent session).",
)
app.add_typer(agent_app, name="agent")


@agent_app.command("log")
def agent_log_cmd(
    section: str = typer.Argument(..., help="Slug or unique substring."),
    message: str = typer.Argument(None, help="Log entry. Omit to read from stdin."),
) -> None:
    """Append a timestamped entry to ``## Agent log`` in the worklog."""
    slug, worklog_path = _resolve_worklog(section)

    if message is None:
        if sys.stdin.isatty():
            typer.echo(
                "error: no message given and stdin is a TTY — "
                "pass a message arg or pipe one in",
                err=True,
            )
            raise typer.Exit(2)
        message = sys.stdin.read()

    if not message.strip():
        typer.echo("error: empty message", err=True)
        raise typer.Exit(2)

    if not worklog_path.exists():
        typer.echo(f"error: worklog not found at {worklog_path}", err=True)
        raise typer.Exit(1)

    try:
        worklog_mod.append_agent_log(worklog_path, message)
    except worklog_mod.WorklogError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1)
    typer.echo(f"appended to Agent log: {slug}")


@app.command(name="doctor")
def doctor(
    boss_doc: Path = typer.Option(Path("BOSS.md"), "--boss-doc"),
) -> None:
    """Report inconsistencies the happy-path verbs ignore."""
    doc = _resolve_boss_doc(boss_doc)
    findings = doctor_mod.diagnose(doc)
    typer.echo(doctor_mod.render(findings))
    if not findings.is_clean():
        raise typer.Exit(1)


def _main() -> None:  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    _main()
