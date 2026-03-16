"""Makefile.py for resend-email project."""

from pymake import sh, task


@task()
def lint():
    """Run ruff linter."""
    sh("ruff check src/resend_email")


@task()
def typecheck():
    """Run pyright type checker."""
    sh("pyright src/resend_email")


@task()
def format():
    """Format code with ruff."""
    sh("ruff format src/resend_email")
    sh("ruff check --fix src/resend_email", check=False)


@task()
def test():
    """Run pytest."""
    sh("pytest -v src/resend_email")


@task(inputs=[lint, typecheck, format, test])
def all():
    pass


task.default(all)
