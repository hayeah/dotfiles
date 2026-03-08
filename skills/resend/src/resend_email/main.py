"""resend-email — CLI for sending emails via Resend."""

from __future__ import annotations

import json
import os
from pathlib import Path

import resend
import typer
from dotenv import load_dotenv

ENV_SECRET = Path.home() / ".env.secret"

app = typer.Typer()


@app.callback()
def main() -> None:
    """Send emails via Resend API."""
    if ENV_SECRET.exists():
        load_dotenv(ENV_SECRET)
    resend.api_key = os.environ.get("RESEND_API_KEY", "")


@app.command()
def send(
    to: list[str] = typer.Option(..., "--to", "-t", help="Recipient email address(es)"),
    subject: str = typer.Option(..., "--subject", "-s", help="Email subject"),
    body: str = typer.Option(..., "--body", "-b", help="Email body (HTML supported)"),
    from_addr: str = typer.Option(
        "onboarding@resend.dev", "--from", "-f", help="Sender address"
    ),
) -> None:
    """Send an email."""
    params: resend.Emails.SendParams = {
        "from": from_addr,
        "to": to,
        "subject": subject,
        "html": body,
    }
    result = resend.Emails.send(params)
    typer.echo(json.dumps(result, indent=2, default=str))


@app.command()
def get(
    email_id: str = typer.Argument(help="Email ID to retrieve"),
) -> None:
    """Get details of a sent email by ID."""
    result = resend.Emails.get(email_id)
    typer.echo(json.dumps(result, indent=2, default=str))


@app.command(name="list")
def list_emails() -> None:
    """List recent sent emails."""
    result = resend.Emails.list()
    typer.echo(json.dumps(result, indent=2, default=str))


@app.command()
def inbox(
    limit: int = typer.Option(20, "--limit", "-n", help="Number of emails to retrieve (max 100)"),
) -> None:
    """List received emails."""
    params: resend.Emails.Receiving.ListParams = {"limit": limit}
    result = resend.Emails.Receiving.list(params)
    typer.echo(json.dumps(result, indent=2, default=str))


@app.command(name="inbox-get")
def inbox_get(
    email_id: str = typer.Argument(help="Received email ID"),
) -> None:
    """Get a received email by ID."""
    result = resend.Emails.Receiving.get(email_id)
    typer.echo(json.dumps(result, indent=2, default=str))


def run() -> None:
    app()


if __name__ == "__main__":
    run()
