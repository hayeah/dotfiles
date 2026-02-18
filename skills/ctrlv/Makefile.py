"""Makefile.py for ctrlv project tasks."""

from pymake import sh, task


@task()
def lint():
    """Run ruff linter."""
    sh("ruff check src/ctrlv")


@task()
def typecheck():
    """Run pyright type checker."""
    sh("pyright src/ctrlv")


@task()
def format():
    """Format code with ruff."""
    sh("ruff format src/ctrlv")
    sh("ruff check --fix src/ctrlv", check=False)


@task()
def test():
    """Run pytest."""
    sh("pytest -v src/ctrlv")


@task(inputs=[lint, typecheck, format, test])
def all():
    """Run all checks."""
    pass


task.default(all)
