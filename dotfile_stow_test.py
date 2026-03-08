"""Tests for DotfileStow."""

from pathlib import Path

import pytest

from dotfile_stow import DotfileStow


def _setup(tmp_path, config_text="[vars]\n"):
    source = tmp_path / "dotfiles"
    target = tmp_path / "home"
    source.mkdir()
    target.mkdir()
    config = tmp_path / ".dotfiles.toml"
    config.write_text(config_text)
    return source, target, config


def test_symlink_plain_file(tmp_path):
    source, target, config = _setup(tmp_path)
    (source / ".zshrc").write_text("# zshrc")

    DotfileStow(source, target, config).apply()

    link = target / ".zshrc"
    assert link.is_symlink()
    assert link.resolve() == (source / ".zshrc").resolve()


def test_nested_dirs_created(tmp_path):
    source, target, config = _setup(tmp_path)
    (source / ".config" / "nvim").mkdir(parents=True)
    (source / ".config" / "nvim" / "init.lua").write_text("-- nvim")

    DotfileStow(source, target, config).apply()

    link = target / ".config" / "nvim" / "init.lua"
    assert link.is_symlink()
    assert link.resolve() == (source / ".config" / "nvim" / "init.lua").resolve()


def test_template_rendering(tmp_path):
    source, target, config = _setup(
        tmp_path, '[vars]\ngitName = "Alice"\ngitEmail = "alice@example.com"\n'
    )
    (source / ".gitconfig.tmpl").write_text("[user]\n    name = $gitName\n    email = $gitEmail\n")

    DotfileStow(source, target, config).apply()

    result = (target / ".gitconfig").read_text()
    assert "Alice" in result
    assert "alice@example.com" in result
    assert not (target / ".gitconfig").is_symlink()
    assert not (target / ".gitconfig.tmpl").exists()


def test_template_overwrites_changed_content(tmp_path):
    source, target, config = _setup(tmp_path, '[vars]\nname = "Bob"\n')
    (source / "file.tmpl").write_text("hello $name")
    (target / "file").write_text("hello Alice")

    DotfileStow(source, target, config).apply()

    assert (target / "file").read_text() == "hello Bob"


def test_template_skips_unchanged(tmp_path):
    source, target, config = _setup(tmp_path, '[vars]\nname = "Bob"\n')
    (source / "file.tmpl").write_text("hello $name")
    (target / "file").write_text("hello Bob")

    actions = DotfileStow(source, target, config).plan()
    assert any(a.status() == "ok" and a.target == target / "file" for a in actions)


def test_missing_template_var_raises(tmp_path):
    source, target, config = _setup(tmp_path)
    (source / "file.tmpl").write_text("hello $missingVar")

    with pytest.raises(KeyError):
        DotfileStow(source, target, config).plan()


def test_symlink_file(tmp_path):
    source, target, config = _setup(tmp_path)
    agents = tmp_path / "AGENTS.md"
    agents.write_text("# Agents")
    (source / ".claude").mkdir()
    (source / ".claude" / "CLAUDE.md.symlink").write_text("../../AGENTS.md")

    DotfileStow(source, target, config).apply()

    link = target / ".claude" / "CLAUDE.md"
    assert link.is_symlink()
    assert link.resolve() == agents.resolve()


def test_symlink_file_rejects_outside_repo(tmp_path):
    source, target, config = _setup(tmp_path)
    (source / "bad.symlink").write_text("../../outside")

    actions = DotfileStow(source, target, config).plan()
    assert any(a.status() == "conflict" and "outside repo root" in a.describe() for a in actions)


def test_skip_existing_correct_symlink(tmp_path):
    source, target, config = _setup(tmp_path)
    (source / ".zshrc").write_text("# zshrc")
    (target / ".zshrc").symlink_to(source / ".zshrc")

    actions = DotfileStow(source, target, config).plan()
    assert all(a.status() == "ok" for a in actions)


def test_conflict_warns_without_force(tmp_path):
    source, target, config = _setup(tmp_path)
    (source / ".zshrc").write_text("# zshrc")
    (target / ".zshrc").write_text("# existing")

    actions = DotfileStow(source, target, config).plan()
    assert any(a.status() == "conflict" for a in actions)


def test_force_overwrites_conflict(tmp_path):
    source, target, config = _setup(tmp_path)
    (source / ".zshrc").write_text("# zshrc")
    (target / ".zshrc").write_text("# existing")

    DotfileStow(source, target, config).apply(force=True)

    link = target / ".zshrc"
    assert link.is_symlink()
    assert link.resolve() == (source / ".zshrc").resolve()


def test_dry_run_no_side_effects(tmp_path):
    source, target, config = _setup(tmp_path)
    (source / ".zshrc").write_text("# zshrc")

    DotfileStow(source, target, config).apply(dry=True)

    assert not (target / ".zshrc").exists()


def test_multiple_file_types(tmp_path):
    """Integration test: plain files, templates, and symlink files together."""
    source, target, config = _setup(tmp_path, '[vars]\nuser = "me"\n')

    (source / ".zshrc").write_text("# zshrc")
    (source / ".gitconfig.tmpl").write_text("user = $user")
    readme = tmp_path / "README.md"
    readme.write_text("# readme")
    (source / ".doc").mkdir()
    (source / ".doc" / "README.md.symlink").write_text("../../README.md")

    DotfileStow(source, target, config).apply()

    assert (target / ".zshrc").is_symlink()
    assert (target / ".gitconfig").read_text() == "user = me"
    assert not (target / ".gitconfig").is_symlink()
    assert (target / ".doc" / "README.md").is_symlink()
    assert (target / ".doc" / "README.md").resolve() == readme.resolve()
