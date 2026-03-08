"""DotfileStow: symlink dotfiles into a target directory with template and symlink-file support."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from string import Template


@dataclass
class Action:
    kind: str  # "symlink", "template", "symlink_file", "skip", "conflict"
    source: Path
    target: Path
    detail: str = ""


class DotfileStow:
    """Manages symlinking dotfiles into a target directory."""

    def __init__(self, source_dir: Path, target_dir: Path, config_path: Path):
        self.source_dir = source_dir.resolve()
        self.target_dir = target_dir.resolve()
        self.config_path = config_path.resolve()
        self.repo_root = self.source_dir.parent

        config = tomllib.loads(self.config_path.read_text())
        self.vars = config.get("vars", {})

    def plan(self) -> list[Action]:
        """Compute actions without side effects."""
        actions: list[Action] = []
        for src in sorted(self.source_dir.rglob("*")):
            if not src.is_file():
                continue
            rel = src.relative_to(self.source_dir)

            if src.suffix == ".tmpl":
                target = self.target_dir / str(rel).removesuffix(".tmpl")
                actions.append(self._plan_template(src, target))
            elif src.suffix == ".symlink":
                target = self.target_dir / str(rel).removesuffix(".symlink")
                actions.append(self._plan_symlink_file(src, target))
            else:
                target = self.target_dir / rel
                actions.append(self._plan_symlink(src, target))

        return actions

    def _plan_symlink(self, source: Path, target: Path) -> Action:
        if target.is_symlink():
            if target.resolve() == source.resolve():
                return Action("skip", source, target, "already linked")
            return Action("conflict", source, target, f"symlink exists → {target.readlink()}")
        if target.exists():
            return Action("conflict", source, target, "file exists")
        return Action("symlink", source, target)

    def _plan_template(self, source: Path, target: Path) -> Action:
        rendered = Template(source.read_text()).substitute(self.vars)
        if target.exists() and not target.is_symlink():
            if target.read_text() == rendered:
                return Action("skip", source, target, "content unchanged")
        return Action("template", source, target, rendered)

    def _plan_symlink_file(self, source: Path, target: Path) -> Action:
        link_target_rel = source.read_text().strip()
        link_target = (source.parent / link_target_rel).resolve()

        if not str(link_target).startswith(str(self.repo_root)):
            return Action("conflict", source, target, f"symlink target {link_target} is outside repo root")

        if target.is_symlink():
            if target.resolve() == link_target:
                return Action("skip", source, target, "already linked")
            return Action("conflict", source, target, f"symlink exists → {target.readlink()}")
        if target.exists():
            return Action("conflict", source, target, "file exists")
        return Action("symlink_file", source, target, str(link_target))

    def apply(self, dry: bool = False, force: bool = False):
        """Execute the plan."""
        actions = self.plan()
        for action in actions:
            if action.kind == "skip":
                continue
            elif action.kind == "conflict":
                if force:
                    print(f"  force {action.target}")
                    if not dry:
                        action.target.unlink(missing_ok=True)
                        # re-plan this single file to get the right action
                        self._execute_for_source(action.source, action.target, dry)
                else:
                    print(f"  SKIP {action.target} ({action.detail})")
            elif action.kind == "symlink":
                print(f"  link {action.target} → {action.source}")
                if not dry:
                    action.target.parent.mkdir(parents=True, exist_ok=True)
                    action.target.symlink_to(action.source)
            elif action.kind == "template":
                print(f"  render {action.target}")
                if not dry:
                    action.target.parent.mkdir(parents=True, exist_ok=True)
                    action.target.write_text(action.detail)
            elif action.kind == "symlink_file":
                link_target = Path(action.detail)
                print(f"  link {action.target} → {link_target}")
                if not dry:
                    action.target.parent.mkdir(parents=True, exist_ok=True)
                    action.target.symlink_to(link_target)

    def _execute_for_source(self, source: Path, target: Path, dry: bool):
        """Re-derive and execute the action for a single source file (used after force-removing conflict)."""
        if source.suffix == ".tmpl":
            rendered = Template(source.read_text()).substitute(self.vars)
            print(f"  render {target}")
            if not dry:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(rendered)
        elif source.suffix == ".symlink":
            link_target_rel = source.read_text().strip()
            link_target = (source.parent / link_target_rel).resolve()
            print(f"  link {target} → {link_target}")
            if not dry:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.symlink_to(link_target)
        else:
            print(f"  link {target} → {source}")
            if not dry:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.symlink_to(source)
