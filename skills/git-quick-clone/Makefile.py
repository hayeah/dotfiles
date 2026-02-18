"""Makefile.py for git-quick-clone project tasks."""

from pymake import sh, task


@task()
def lint():
    """Run ruff linter."""
    sh("ruff check src/git_quick_clone")


@task()
def typecheck():
    """Run pyright type checker."""
    sh("pyright src/git_quick_clone")


@task()
def format():
    """Format code with ruff."""
    sh("ruff format src/git_quick_clone")
    sh("ruff check --fix src/git_quick_clone", check=False)


@task()
def test():
    """Run pytest."""
    sh("pytest -v src/git_quick_clone")


@task(inputs=[lint, typecheck, format, test])
def all():
    """Run all checks."""
    pass


task.default(all)
