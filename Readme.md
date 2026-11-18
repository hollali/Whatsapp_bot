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
python run.py
```

CLI:

```bash
python -m app.cli users_create --email admin@example.com --password secret
python -m app.cli send --phone +233505036932 --message "Hi"
python -m app.cli stats
```

Tests:

```bash
python -m pytest tests  # if pytest installed
# or
python -m unittest discover -s tests
```

## API

Base: `/api/v1`. Endpoints: `/auth`, `/contacts`, `/messages`, `/campaigns`, `/schedules`, `/templates`, `/analytics`, `/health`.

## Docker

```bash
docker-compose up --build
```
