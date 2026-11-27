# WhatsApp Bot Platform

A full-stack WhatsApp messaging platform: scheduling, campaigns, contacts, templates, analytics, REST API, web dashboard, CLI, and background worker.

## Features

- Multi-provider sending (pywhatkit, Twilio/Business API stubs)
- Scheduled & instant messages, bulk send, campaigns
- Contacts & groups, CSV import
- Jinja2 message templates with variables
- REST API (v1) with session + API keys
- Web dashboard
- Background scheduler with retries
- Analytics & delivery logs
- Real-time job updates via SocketIO
- Docker & docker-compose

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# set a long random SECRET_KEY in .env before deploying
python run.py
```

CLI (arguments are positional; `schedule`, `import-contacts` and `stats` accept `--user`):

```bash
python -m app.cli users-create admin@example.com 'long-password'
python -m app.cli send +233505036932 "Hi"
python -m app.cli schedule +233505036932 "Follow up" 2026-12-01T10:00:00 --user admin@example.com
python -m app.cli import-contacts contacts.csv --user admin@example.com
python -m app.cli stats --user admin@example.com
```

Tests:

```bash
python -m pytest tests  # if pytest installed
# or
python -m unittest discover -s tests
```

## API

Base: `/api/v1`. Endpoints: `/auth`, `/contacts`, `/messages`, `/campaigns`, `/schedules`, `/templates`, `/analytics`, `/health`.

Browser requests use the logged-in session. Scripts can create a key via `POST /api/v1/auth/api-keys` and pass it as `Authorization: Bearer <key>` or `X-API-Key: <key>`. Keep the returned key safe; only its hash is stored.

## Docker

```bash
docker-compose up --build
docker-compose exec web flask db upgrade
```

Set `AUTO_CREATE_TABLES=false` to rely on migrations only.
