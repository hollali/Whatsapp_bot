import csv
import os
import uuid

import typer

os.environ.setdefault("ENABLE_SCHEDULER", "false")

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.utils import parse_utc  # noqa: E402

cli = typer.Typer(help="WhatsApp Bot Platform CLI")


def _context():
    return create_app().app_context()


def _user(identifier=None):
    from app.models.user import User
    query = User.query
    if identifier:
        user = query.filter_by(email=identifier.lower()).first() or db.session.get(User, identifier)
    else:
        user = query.first()
    if not user:
        typer.echo("No users exist. Create one with users-create.")
        raise typer.Exit(1)
    return user


@cli.command()
def send(phone: str, message: str, provider: str = "pywhatkit", instant: bool = True):
    """Send a message immediately."""
    from app.services.sender import SenderService
    with _context():
        result = SenderService(provider).send(phone, message, instant=instant)
    typer.echo(f"Sent: {result}")


@cli.command()
def schedule(phone: str, message: str, run_at: str, provider: str = "pywhatkit",
             user_email: str = typer.Option(None, "--user", help="User email")):
    """Schedule a message (run_at ISO datetime)."""
    from app.services.queue import QueueService
    with _context():
        try:
            when = parse_utc(run_at, "run_at")
        except Exception as exc:
            raise typer.BadParameter(str(exc))
        user = _user(user_email)
        job = QueueService().enqueue(user.id, phone, message, run_at=when, provider=provider)
        job_id = job.id
    typer.echo(f"Scheduled job {job_id}")


@cli.command("import-contacts")
def import_contacts(file: str, user_email: str = typer.Option(None, "--user", help="User email")):
    """Import contacts from CSV (phone,name,email,tags)."""
    from app.models.contact import Contact
    from app.utils import phone_field
    from werkzeug.exceptions import BadRequest
    with _context():
        user = _user(user_email)
        existing = {c.phone for c in Contact.query.filter_by(user_id=user.id).all()}
        created = skipped = 0
        with open(file, encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                try:
                    phone = phone_field(row)
                except BadRequest:
                    skipped += 1
                    continue
                if phone in existing:
                    skipped += 1
                    continue
                db.session.add(Contact(user_id=user.id, phone=phone,
                                       name=(row.get("name") or "").strip() or None,
                                       email=(row.get("email") or "").strip() or None,
                                       tags=(row.get("tags") or "").strip() or None))
                existing.add(phone)
                created += 1
        db.session.commit()
    typer.echo(f"Imported {created} contacts ({skipped} skipped)")


@cli.command()
def stats(user_email: str = typer.Option(None, "--user", help="User email")):
    """Show delivery stats."""
    from app.services.queue import QueueService
    with _context():
        user = _user(user_email)
        result = QueueService().stats(user_id=user.id)
    typer.echo(result)


@cli.command("users-create")
def users_create(email: str, password: str, name: str = ""):
    """Create a user."""
    from app.models.user import User
    with _context():
        email = email.lower()
        if User.query.filter_by(email=email).first():
            typer.echo("User exists")
            raise typer.Exit(1)
        if len(password) < 8:
            typer.echo("Password must be at least 8 characters")
            raise typer.Exit(1)
        user = User(id=str(uuid.uuid4()), email=email, name=name or email.split("@")[0])
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        user_id = user.id
    typer.echo(f"Created user {user_id}")


if __name__ == "__main__":
    cli()
