"""Makefile.py for shell-helper project tasks."""

from pymake import sh, task


@task()
def lint():
    """Run ruff linter."""
    sh("ruff check src/shell_helper")


@task()
def typecheck():
    """Run pyright type checker."""
    sh("pyright src/shell_helper")


@task()
def format():
    """Format code with ruff."""
    sh("ruff format src/shell_helper")
    sh("ruff check --fix src/shell_helper", check=False)


@task()
def test():
    """Run pytest."""
    sh("pytest -v src/shell_helper")


@task(inputs=[lint, typecheck, format, test])
def all():
    """Run all checks."""
    pass


task.default(all)
