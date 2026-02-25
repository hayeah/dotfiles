"""Makefile.py for imagegen project tasks."""

from pymake import sh, task


@task()
def lint():
    """Run ruff linter."""
    sh("ruff check src/imagegen")


@task()
def typecheck():
    """Run pyright type checker."""
    sh("pyright src/imagegen")


@task()
def format():
    """Format code with ruff."""
    sh("ruff format src/imagegen")
    sh("ruff check --fix src/imagegen", check=False)


@task()
def test():
    """Run pytest."""
    sh("pytest -v src/imagegen")


@task(inputs=[lint, typecheck, format, test])
def all():
    """Run all checks."""
    pass


task.default(all)
