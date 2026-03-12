# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

A local self-service platform for provisioning OpenClaw agents on macOS. Users fill a web form; the backend writes `~/.openclaw/openclaw.json` and the running OpenClaw gateway auto-reloads via its built-in file watcher.

**Stack:** Python · FastAPI · SQLite · SQLModel · Single-file HTML frontend

---

## Planned Directory Structure

```
openclaw-agent-selfservice/
├── backend/
│   ├── main.py              # FastAPI app + Uvicorn entry point
│   ├── models.py            # Pydantic + SQLModel schemas
│   ├── openclaw_manager.py  # openclaw.json read/write/atomic-write
│   ├── database.py          # SQLite setup
│   └── config.py            # Settings (paths, env vars)
├── frontend/
│   └── index.html           # Single-file dashboard
├── requirements.txt
├── .env.example
└── PLAN.md
```

---

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run backend (dev)
uvicorn backend.main:app --reload --port 3000

# Run tests
pytest
pytest tests/test_api.py::test_create_agent  # single test
```

---

## OpenClaw Integration

### Config file
`~/.openclaw/openclaw.json` — path overrideable via `OPENCLAW_CONFIG_PATH` env var.

### Auto-reload (critical!)
OpenClaw's gateway watches `openclaw.json` with chokidar and reloads automatically:
- Changes to `agents` and `bindings` → **no-op reload**: config updated in gateway memory, no channel restart
- Changes to `channels.telegram` → **Telegram channel hot-restart**: the bot restarts with the new account/token config

**Do NOT call `openclaw gateway restart`** — writing the JSON file atomically is sufficient and causes zero downtime.

### openclaw.json structure for agent provisioning

When creating a new agent with slug `my-agent`, three sections must be updated:

```json
{
  "agents": {
    "list": [
      {
        "id": "my-agent",
        "workspace": "/Users/<user>/.openclaw/workspaces/my-agent",
        "model": { "primary": "google/gemini-2.5-flash-lite" }
      }
    ]
  },
  "channels": {
    "telegram": {
      "accounts": {
        "my-agent": { "botToken": "${AGENT_BOT_TOKEN_MY_AGENT}" }
      }
    }
  },
  "bindings": [
    {
      "agentId": "my-agent",
      "match": { "channel": "telegram", "accountId": "my-agent" }
    }
  ]
}
```

Note: `agents.defaults.sandbox` is already set globally in the existing config (scope: `agent`, image: `openclaw-sandbox-browser:bookworm-slim`, network: `openclaw-n8n`). New agents inherit it automatically — do not write sandbox config per agent.

### Atomic write pattern
Always write `openclaw.json` via temp file + rename to avoid corrupt reads:
```python
import json, os, tempfile

def atomic_write_json(path: str, data: dict) -> None:
    dir_ = os.path.dirname(path)
    with tempfile.NamedTemporaryFile("w", dir=dir_, delete=False, suffix=".tmp") as f:
        json.dump(data, f, indent=2)
        tmp = f.name
    os.replace(tmp, path)
```

### Telegram bot token env convention
Slug `my-rag-agent` → env var `AGENT_BOT_TOKEN_MY_RAG_AGENT` (uppercase, hyphens → underscores).
The token is referenced in `openclaw.json` as `"${AGENT_BOT_TOKEN_MY_RAG_AGENT}"` — OpenClaw expands env vars at runtime.

---

## Environment Variables (.env)

```bash
OPENCLAW_CONFIG_PATH=/Users/<user>/.openclaw/openclaw.json
OPENCLAW_WORKSPACES_DIR=/Users/<user>/.openclaw/workspaces
OPENCLAW_GATEWAY_URL=http://localhost:18789
OPENCLAW_GATEWAY_TOKEN=<token>
PLATFORM_PORT=3000

# Per-agent Telegram tokens (added manually):
# AGENT_BOT_TOKEN_MY_RAG_AGENT=<bot_token>
```

---

## Agent Slug Validation

Agent IDs must match `[a-z0-9-]+` (lowercase, digits, hyphens only). Validate before writing to config.

---

## Implementation Phases (from PLAN.md)

1. **Backend Core** – FastAPI skeleton, SQLite, `openclaw_manager.py`, `POST/GET /api/agents`
2. **Delete + Status** – `DELETE /api/agents/{id}`, `GET /api/openclaw/status` (via `pgrep`), `POST /api/openclaw/reload`
3. **Frontend** – Single-file HTML dashboard with agent form, slug auto-generation, polling, status badge
4. **QA** – pytest suite covering all endpoints, atomic-write concurrency, smoke test (create→verify JSON→delete)
