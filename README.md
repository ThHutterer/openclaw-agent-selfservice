# openclaw-agent-selfservice

A local self-service platform for provisioning [OpenClaw](https://openclaw.ai) agents on macOS. Users fill out a web form; the backend writes `~/.openclaw/openclaw.json` and the running OpenClaw gateway auto-reloads via its built-in file watcher.

**Stack:** Python · FastAPI · SQLite · SQLModel · Single-file HTML frontend

---

## Architecture

```
Browser (http://localhost:3000)
        │ REST
FastAPI Backend
  ├── Agent Registry (SQLite)
  ├── openclaw.json Manager (atomic read/write)
  └── OpenClaw status/reload
        │ writes config
OpenClaw Gateway (port 18789)
  └── manages sandboxed agent containers (Docker)
```

The platform never touches Docker directly — it only writes `openclaw.json`. OpenClaw's chokidar file watcher picks up changes automatically with zero downtime.

---

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your paths and tokens

# 3. Run backend
python3 -m uvicorn backend.main:app --reload --port 3000
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## Environment Variables

```bash
OPENCLAW_CONFIG_PATH=/Users/<you>/.openclaw/openclaw.json
OPENCLAW_WORKSPACES_DIR=/Users/<you>/.openclaw/workspaces
OPENCLAW_GATEWAY_URL=http://localhost:18789
OPENCLAW_GATEWAY_TOKEN=<your_gateway_token>
PLATFORM_PORT=3000

# Per-agent Telegram bot tokens (add manually after creating an agent):
# AGENT_BOT_TOKEN_MY_AGENT=<bot_token>
```

---

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/agents` | Create a new agent |
| `GET` | `/api/agents` | List all agents |
| `GET` | `/api/agents/{id}` | Get agent details |
| `DELETE` | `/api/agents/{id}` | Delete an agent |
| `GET` | `/api/openclaw/status` | Check if OpenClaw gateway is running |
| `POST` | `/api/openclaw/reload` | Trigger manual reload |

Agent slugs must match `[a-z0-9-]+`.

---

## Telegram Integration

Each agent gets a dedicated Telegram bot. After creating an agent with slug `my-agent`:

1. Create a Telegram bot via [@BotFather](https://t.me/botfather)
2. Add the token to your `.env`: `AGENT_BOT_TOKEN_MY_AGENT=<token>`
3. The dashboard shows a green/red indicator per agent for token status

The `openclaw.json` references tokens as `${AGENT_BOT_TOKEN_MY_AGENT}` — OpenClaw expands them at runtime.

---

## Tests

```bash
python3 -m pytest tests/ -x --tb=short
```

17 tests covering all API endpoints, atomic write concurrency, and a full create→verify→delete smoke test.

---

## Project Structure

```
backend/
  main.py              # FastAPI app, all routes
  models.py            # SQLModel table + Pydantic schemas
  database.py          # SQLite setup
  config.py            # Settings via pydantic-settings
  openclaw_manager.py  # openclaw.json read/write/atomic-write
frontend/
  index.html           # Single-file vanilla JS dashboard
tests/
  conftest.py
  test_api.py
  test_openclaw_manager.py
```
