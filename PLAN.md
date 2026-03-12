# PLAN.md – Open Cloud Self-Service Platform
## Claude Code Agent Team Blueprint

> **Ziel:** Eine lokale Self-Service-Plattform auf dem Mac. Nutzer bestellen über ein Web-Dashboard neue Agents. OpenClaw läuft nativ auf dem Mac und verwaltet das Sandboxing selbst – jeder Agent bekommt seinen eigenen Docker-Container via OpenClaw's eingebautem Sandbox-System. Die Platform-App selbst ist ein einfaches Python/FastAPI-Backend das ausschließlich die `openclaw.json` manipuliert.

---

## 1. Systemübersicht

```
┌─────────────────────────────────────────────────────────────┐
│                    Browser (User)                           │
│              http://localhost:3000 (Dashboard)              │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP / REST
┌────────────────────▼────────────────────────────────────────┐
│         Platform Backend (FastAPI / Python)                 │
│  - Agent Registry (SQLite)                                  │
│  - openclaw.json Manager (lesen/schreiben)                  │
│  - OpenClaw Process Manager (reload trigger)                │
└────────────────────┬────────────────────────────────────────┘
                     │ schreibt config + reloads
┌────────────────────▼────────────────────────────────────────┐
│         OpenClaw (nativ auf Mac, als Prozess)               │
│  - Gateway Port: 18789                                      │
│  - Verwaltet Agents + Sandboxes selbst                      │
└───────┬─────────────────────────────┬───────────────────────┘
        │ spawnt via Docker SDK        │
┌───────▼──────────┐        ┌─────────▼──────────┐
│  Sandbox         │        │  Sandbox            │  ...
│  agent-alpha     │        │  agent-beta         │
│  (bookworm-slim) │        │  (bookworm-slim)    │
│  Network:        │        │  Network:           │
│  openclaw-n8n    │        │  openclaw-n8n       │
└──────────────────┘        └─────────────────────┘
```

**Kernprinzip:** Die Platform-App berührt Docker nie direkt. Sie schreibt nur `openclaw.json` und triggert OpenClaw-Reload. OpenClaw übernimmt das Container-Management.

---

## 2. Wie OpenClaw Sandboxing funktioniert (aus Doku)

Relevante Config-Optionen die wir pro Agent steuern:

```json
{
  "agents": {
    "defaults": {
      "sandbox": {
        "mode": "all",           // alle Sessions sandboxed
        "scope": "agent",        // ein Container pro Agent
        "workspaceAccess": "rw", // Agent kann in sein Workspace schreiben
        "docker": {
          "image": "openclaw-sandbox-browser:bookworm-slim",
          "network": "openclaw-n8n"
        }
      }
    },
    "list": [
      {
        "id": "agent-slug",
        "workspace": "/Users/<user>/.openclaw/workspaces/agent-slug"
        // Sandbox erbt defaults, kann hier überschrieben werden
      }
    ]
  }
}
```

**Scope "agent":** Ein Container pro Agent-ID → perfekt für Isolation zwischen Kunden.

---

## 3. Datenmodell – Agent Registry (SQLite)

```python
# agents Tabelle
{
  "id":            "uuid4",
  "agent_id":      "werchota-rag",          # OpenClaw agent id (slug, unique)
  "display_name":  "werchota RAG Agent",
  "owner_name":    "Thomas Gosch",
  "organization":  "werchota.ai",
  "description":   "Hilft bei RAG-Pipelines",
  "workspace":     "/Users/.../workspaces/werchota-rag",
  "model_primary": "google/gemini-2.5-flash-lite",
  "status":        "active | deleted",
  "created_at":    "ISO timestamp"
}
```

---

## 4. Platform API (FastAPI)

```
POST   /api/agents              → Neuen Agent anlegen
GET    /api/agents              → Alle Agents auflisten
GET    /api/agents/{id}         → Agent-Details
DELETE /api/agents/{id}         → Agent entfernen

GET    /api/openclaw/status     → Ist OpenClaw-Prozess alive?
POST   /api/openclaw/reload     → openclaw reload / restart trigger
```

---

## 5. Agent-Spawn-Flow

```
User füllt Form aus: Name, Agent-ID (slug), Beschreibung, Organisation
       │
       ▼
POST /api/agents
       │
  1. Input validieren
     - agent_id: nur [a-z0-9-], unique prüfen
     - owner_name, organization: non-empty
  2. Workspace-Verzeichnis anlegen:
     mkdir ~/.openclaw/workspaces/{agent_id}
  3. openclaw.json laden (json.load)
  4. Neuen Eintrag in agents.list appenden:
     {
       "id": "{agent_id}",
       "workspace": "~/.openclaw/workspaces/{agent_id}",
       "model": {"primary": "google/gemini-2.5-flash-lite"}
     }
  5. System-Prompt in Workspace schreiben (PROMPT.md)
  6. Telegram-Binding + Account-Eintrag in openclaw.json hinzufügen
     (botToken referenziert ${AGENT_BOT_TOKEN_<SLUG>})
  7. openclaw.json atomar zurückschreiben (tempfile + rename)
  7. OpenClaw reload triggern
  8. Agent in SQLite speichern
  9. Response: { agent_id, status: "active", workspace }
       │
       ▼
Dashboard zeigt neuen Agent
```

---

## 6. OpenClaw Reload-Strategie

**Kein manueller Restart nötig!** OpenClaw überwacht `openclaw.json` automatisch via chokidar File-Watcher und reagiert wie folgt:

| Geänderte Sektion | Reload-Verhalten |
|---|---|
| `agents`, `bindings` | **No-op**: Config wird im Gateway-Memory aktualisiert, kein Neustart |
| `channels.telegram` | **Hot-Reload**: Telegram-Bot startet neu mit neuen Account-Daten |

→ **Einfach die Datei atomar schreiben – das reicht.** Null Downtime.

```python
# Kein subprocess.run(["openclaw", "gateway", "restart"]) nötig!
# Atomic write (siehe openclaw_manager.py) triggert den Reload automatisch.
```

Das `POST /api/openclaw/reload`-Endpoint (für manuelles Reload durch den User) kann einen `SIGHUP` senden oder die Datei neu schreiben – aber im Normalfall ist kein expliziter Reload-Call nach `POST/DELETE /api/agents` nötig.

---

## 7. Bestehende Config korrekt erweitern

Aus deiner `openclaw.json` sind folgende Defaults bereits gesetzt:

```json
"sandbox": {
  "mode": "all",
  "scope": "agent",
  "workspaceAccess": "rw",
  "docker": {
    "image": "openclaw-sandbox-browser:bookworm-slim",
    "network": "openclaw-n8n"
  }
}
```

Neue Agents erben diese Defaults automatisch. Wir müssen pro Agent nur hinzufügen:
- `id` (slug)
- `workspace` (Pfad)
- Optional: `model.primary` override

Das ist minimal-invasiv – kein Anfassen der Sandbox-Config nötig.


---

## 8. Telegram-Binding

Token wird **manuell ins `.env`** eingetragen. Das Backend referenziert ihn als `${AGENT_BOT_TOKEN_<SLUG>}` in der `openclaw.json`. Das Dashboard zeigt pro Agent ob der Token gesetzt ist (🟢 / 🔴).

**openclaw.json-Einträge die beim Agent-Spawn geschrieben werden:**

```json
// agents.list[] – neuer Eintrag
{ "id": "new-agent", "workspace": "/Users/.../.openclaw/workspaces/new-agent" }

// bindings[] – neuer Eintrag
{ "agentId": "new-agent", "match": { "channel": "telegram", "accountId": "new-agent" } }

// channels.telegram.accounts – neuer Eintrag
"new-agent": { "botToken": "${AGENT_BOT_TOKEN_NEW_AGENT}" }
```

**Env-Variable Konvention:** Slug `my-rag-agent` → `AGENT_BOT_TOKEN_MY_RAG_AGENT` (uppercase, Bindestriche → Underscores).

**Dashboard Status-Check:** Backend liest `.env`, prüft ob Variable gesetzt → zeigt 🟢 Token gesetzt / 🔴 Token fehlt.

---

## 9. Dashboard UI

**Formular:**
- Dein Name (owner_name)
- Agent-Anzeigename (display_name)
- Agent-ID (slug, auto-generiert aus display_name, editierbar)
- Organisation
- Beschreibung (Textarea → wird als System-Prompt-Basis verwendet)
- Modell-Auswahl (Dropdown: flash-lite / pro-preview)

**Agent-Liste:**
- Tabelle: Agent-ID | Organisation | Owner | Erstellt | Status | Telegram
- Status-Badge: 🟢 active / 🔴 deleted
- Telegram-Spalte: 🟢 Token gesetzt / 🔴 Token fehlt
- Action: Agent löschen

**Status-Panel:**
- OpenClaw-Prozess Status (alive / dead)
- Gateway-URL: `http://localhost:18789`
- Reload-Button

---

## 10. Verzeichnisstruktur

```
open-cloud-platform/
├── backend/
│   ├── main.py                  # FastAPI App + Uvicorn
│   ├── models.py                # Pydantic + SQLModel
│   ├── openclaw_manager.py      # openclaw.json lesen/schreiben + reload
│   ├── database.py              # SQLite Setup
│   └── config.py                # Settings (Pfade, Tokens)
├── frontend/
│   └── index.html               # Single-file Dashboard
├── requirements.txt
├── .env.example
└── PLAN.md
```

---

## 11. Konfiguration (.env)

```bash
# Pfad zur openclaw.json auf dem Mac
OPENCLAW_CONFIG_PATH=/Users/<yourname>/.openclaw/openclaw.json

# Workspaces-Verzeichnis (wird auto-angelegt)
OPENCLAW_WORKSPACES_DIR=/Users/<yourname>/.openclaw/workspaces

# Gateway
OPENCLAW_GATEWAY_URL=http://localhost:18789
OPENCLAW_GATEWAY_TOKEN=<dein_gateway_token>

# Platform-Backend Port
PLATFORM_PORT=3000

# Telegram Bot Tokens pro Agent (manuell eintragen)
# Konvention: AGENT_BOT_TOKEN_<SLUG_UPPERCASE_UNDERSCORED>
# AGENT_BOT_TOKEN_MY_RAG_AGENT=<bot_token>
# AGENT_BOT_TOKEN_SUPPORT_BOT=<bot_token>
```

---

## 12. Implementierungsreihenfolge (Claude Code Team)

### Phase 1 – Backend Core (Backend-Agent)
- [ ] FastAPI-Grundgerüst, Health-Endpoint, CORS
- [ ] SQLite-Setup mit SQLModel
- [ ] `openclaw_manager.py`: JSON lesen, Agent hinzufügen, atomar schreiben
- [ ] OpenClaw Reload-Mechanismus (SIGHUP oder Gateway-Endpoint)
- [ ] POST /api/agents + GET /api/agents

### Phase 2 – Delete + Status (Backend-Agent)
- [ ] DELETE /api/agents/{id}: aus JSON entfernen + Workspace optional löschen
- [ ] GET /api/openclaw/status: Prozess-Check via `pgrep`
- [ ] POST /api/openclaw/reload: manueller Trigger

### Phase 3 – Frontend (Frontend-Agent)
- [ ] Single-file HTML Dashboard
- [ ] Formular mit slug-Auto-Generierung (JS)
- [ ] Agent-Liste mit Polling alle 5s
- [ ] OpenClaw-Status-Badge + Reload-Button

### Phase 4 – QA (QA-Agent)
- [ ] pytest-Suite für alle API-Endpunkte
- [ ] Atomic-Write-Test (gleichzeitige Requests)
- [ ] Smoke-Test: Agent anlegen → JSON prüfen → Agent löschen

---

## 13. Offene Punkte / Zu klären

- [ ] **Auth auf Dashboard:** Lokal ohne Auth für MVP OK?

---

*Stack: Python · FastAPI · SQLite · SQLModel · Single-file HTML*
*OpenClaw: nativ auf Mac – Sandboxing via eingebautem Docker-Support*
*Kein direktes docker-py – OpenClaw übernimmt Container-Management vollständig*
