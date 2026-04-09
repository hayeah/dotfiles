"""Typer entry point for the `boss` CLI."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

from . import (
    agentboss,
    briefing,
    bossdoc,
    doctor as doctor_mod,
    lgtm as lgtm_mod,
    ls as ls_mod,
    workspace,
)

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Workflow CLI for the boss skill — workspaces, BOSS.md ↔ agentboss join, lgtm gating.",
)


def _resolve_boss_doc(path: Path | None) -> Path:
    if path is None:
        path = Path("BOSS.md")
    return path.resolve()


@app.command()
def spawn(
    section: str = typer.Argument(..., help="Slug or unique substring of a section header."),
    mode: str = typer.Option("worktree", "--mode", help="worktree | main-repo"),
    boss_doc: Path = typer.Option(Path("BOSS.md"), "--boss-doc", help="Path to BOSS.md."),
    claude_args: list[str] = typer.Option(
        None,
        "--claude-arg",
        help="Extra arg to pass to claude (repeatable). Defaults to --dangerously-skip-permissions.",
    ),
) -> None:
    """Set up a workspace for a section and spawn an agent inside it."""
    if mode not in ("worktree", "main-repo"):
        typer.echo(f"error: invalid --mode {mode!r} (use 'worktree' or 'main-repo')", err=True)
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
    if lay.root.is_dir():
        live = agentboss.session_for_cwd(lay.root)
        if live is not None:
            typer.echo(
                f"error: workspace {s.slug!r} already has a live agentboss session "
                f"(key={live.get('key', '?')}). refusing to spawn a duplicate.",
                err=True,
            )
            raise typer.Exit(1)

    workspace.create(s.slug, s.header, mode)

    cmd = ["claude"]
    if not claude_args:
        cmd.append("--dangerously-skip-permissions")
    else:
        cmd.extend(claude_args)

    try:
        descriptor = agentboss.run(cwd=lay.root, command=cmd, detector="claude")
    except agentboss.AgentbossError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1)

    key = descriptor.get("key") or descriptor.get("short_id") or "?"

    msg = briefing.render(slug=s.slug, header=s.header, mode=mode, boss_doc=doc)
    try:
        agentboss.send(key, msg)
    except agentboss.AgentbossError as e:
        typer.echo(f"warning: spawned agent {key} but briefing send failed: {e}", err=True)

    typer.echo(f"spawned: slug={s.slug} key={key} workspace={lay.root}")


@app.command(name="ls")
def ls_cmd(
    boss_doc: Path = typer.Option(Path("BOSS.md"), "--boss-doc"),
    json_out: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """Wide read: BOSS.md ↔ workspace ↔ agentboss join."""
    doc = _resolve_boss_doc(boss_doc)
    try:
        rows = ls_mod.collect(doc)
    except bossdoc.BossDocError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1)

    if json_out:
        typer.echo(json.dumps([r.to_json() for r in rows], indent=2))
        return

    if not rows:
        typer.echo("(no sections in BOSS.md)")
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

    for r in results:
        marker = "OK" if r.ok else "FAIL"
        typer.echo(f"{marker}  {r.label}: {r.message}")


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
