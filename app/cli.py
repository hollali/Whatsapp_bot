import typer
from datetime import datetime
from typing import Optional, List

from app import create_app
from app.services.queue import QueueService
from app.services.sender import SenderService

app = create_app()
queue = QueueService()

cli = typer.Typer(help="WhatsApp Bot Platform CLI")


@cli.command()
def send(phone: str, message: str, provider: str = "pywhatkit", instant: bool = True):
    """Send a message immediately."""
    s = SenderService(provider)
    res = s.send(phone, message, instant=instant)
    typer.echo(f"Sent: {res}")


@cli.command()
def schedule(phone: str, message: str, run_at: str, provider: str = "pywhatkit"):
    """Schedule a message (run_at ISO datetime)."""
    dt = datetime.fromisoformat(run_at)
    # need user; use first user or create? For CLI, require user id via env? Use system user
    from app.models.user import User
    u = User.query.first()
    if not u:
        typer.echo("No users exist. Register first via web/api.")
        raise typer.Exit(1)
    job = queue.enqueue(u.id, phone, message, run_at=dt, provider=provider)
    typer.echo(f"Scheduled job {job.id} at {dt}")


@cli.command()
def import_contacts(file: str):
    """Import contacts from CSV (phone,name)."""
    import csv
    from app.models.contact import Contact
    from app.extensions import db
    u = None
    from app.models.user import User
    u = User.query.first()
    if not u:
        typer.echo("No users exist.")
        raise typer.Exit(1)
    with open(file) as f:
        reader = csv.DictReader(f)
        n = 0
        for row in reader:
            c = Contact(user_id=u.id, phone=row.get("phone"), name=row.get("name"))
            db.session.add(c)
            n += 1
        db.session.commit()
    typer.echo(f"Imported {n} contacts")


@cli.command()
def stats():
    """Show delivery stats."""
    s = queue.stats()
    typer.echo(s)


@cli.command()
def users_create(email: str, password: str, name: str = ""):
    """Create a user."""
    from app.models.user import User
    from app.extensions import db
    if User.query.filter_by(email=email).first():
        typer.echo("User exists")
        raise typer.Exit(1)
    u = User(email=email, name=name)
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    typer.echo(f"Created user {u.id}")


if __name__ == "__main__":
    cli()
