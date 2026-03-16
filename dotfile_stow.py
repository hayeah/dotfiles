"""DotfileStow: symlink dotfiles into a target directory with template and symlink-file support."""

from __future__ import annotations

import tomllib
from abc import ABC, abstractmethod
from pathlib import Path
from string import Template


class Action(ABC):
    """Base class for dotfile actions."""

    def __init__(self, source: Path, target: Path):
        self.source = source
        self.target = target

    @abstractmethod
    def status(self) -> str:
        """Return "ok", "update", or "conflict"."""

    @abstractmethod
    def describe(self) -> str:
        """Human-readable description of what this action does."""

    @abstractmethod
    def execute(self):
        """Apply the action (create/update the target)."""

    def apply(self, dry: bool = False, force: bool = False):
        st = self.status()
        if st == "ok":
            return
        if st == "conflict" and not force:
            print(f"  SKIP {self.target} ({self.describe()})")
            return
        if st == "conflict":
            print(f"  force {self.target}")
            if not dry:
                self.target.unlink(missing_ok=True)

        print(f"  {self.describe()}")
        if not dry:
            self.target.parent.mkdir(parents=True, exist_ok=True)
            self.execute()


class SymlinkAction(Action):
    """Symlink a plain file into the target directory."""

    def status(self) -> str:
        if self.target.is_symlink():
            if self.target.resolve() == self.source.resolve():
                return "ok"
            return "conflict"
        if self.target.exists():
            return "conflict"
        return "update"

    def describe(self) -> str:
        if self.status() == "conflict":
            if self.target.is_symlink():
                return f"symlink exists → {self.target.readlink()}"
            return "file exists"
        return f"link {self.target} → {self.source}"

    def execute(self):
        self.target.symlink_to(self.source)


class TemplateAction(Action):
    """Render a template and write the result."""

    def __init__(self, source: Path, target: Path, rendered: str):
        super().__init__(source, target)
        self.rendered = rendered

    def status(self) -> str:
        if self.target.is_symlink():
            return "conflict"
        if self.target.exists():
            if self.target.read_text() == self.rendered:
                return "ok"
            # Content changed — always overwrite, no conflict
        return "update"

    def describe(self) -> str:
        if self.status() == "conflict":
            return f"symlink exists → {self.target.readlink()}"
        return f"render {self.target}"

    def execute(self):
        self.target.write_text(self.rendered)


class SymlinkFileAction(Action):
    """Create a symlink based on a .symlink file's content."""

    def __init__(self, source: Path, target: Path, link_to: Path, error: str | None = None):
        super().__init__(source, target)
        self.link_to = link_to
        self.error = error

    def status(self) -> str:
        if self.error:
            return "conflict"
        if self.target.is_symlink():
            if self.target.resolve() == self.link_to:
                return "ok"
            return "conflict"
        if self.target.exists():
            return "conflict"
        return "update"

    def describe(self) -> str:
        if self.error:
            return self.error
        if self.status() == "conflict":
            if self.target.is_symlink():
                return f"symlink exists → {self.target.readlink()}"
            return "file exists"
        return f"link {self.target} → {self.link_to}"

    def execute(self):
        self.target.symlink_to(self.link_to)


class DotfileStow:
    """Manages symlinking dotfiles into a target directory."""

    def __init__(self, source_dir: Path, target_dir: Path, config_path: Path):
        self.source_dir = source_dir.resolve()
        self.target_dir = target_dir.resolve()
        self.repo_root = self.source_dir.parent

        config = tomllib.loads(config_path.resolve().read_text())
        self.vars = config.get("vars", {})

    def plan(self) -> list[Action]:
        """Compute actions without side effects."""
        actions: list[Action] = []
        for src in sorted(self.source_dir.rglob("*")):
            if not src.is_file():
                continue
            rel = src.relative_to(self.source_dir)
            if rel.parts[0] == ".git":
                continue

            if src.suffix == ".tmpl":
                target = self.target_dir / str(rel).removesuffix(".tmpl")
                rendered = Template(src.read_text()).substitute(self.vars)
                actions.append(TemplateAction(src, target, rendered))
            elif src.suffix == ".symlink":
                target = self.target_dir / str(rel).removesuffix(".symlink")
                link_target_rel = src.read_text().strip()
                link_target = (src.parent / link_target_rel).resolve()
                error = None
                if not str(link_target).startswith(str(self.repo_root)):
                    error = f"symlink target {link_target} is outside repo root"
                actions.append(SymlinkFileAction(src, target, link_target, error))
            else:
                target = self.target_dir / rel
                actions.append(SymlinkAction(src, target))

        return actions

    def apply(self, dry: bool = False, force: bool = False):
        """Execute the plan."""
        for action in self.plan():
            action.apply(dry=dry, force=force)
