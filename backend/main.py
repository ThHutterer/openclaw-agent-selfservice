import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from backend.config import settings
from backend.database import create_db_and_tables, get_session
from backend.models import Agent, AgentCreate, AgentRead
from backend.openclaw_manager import (
    add_agent_to_config,
    check_telegram_token,
    get_openclaw_status,
    load_config,
    remove_agent_from_config,
    save_config,
)

SLUG_RE = re.compile(r"^[a-z0-9-]+$")


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _agent_to_read(agent: Agent) -> AgentRead:
    return AgentRead(
        **agent.model_dump(),
        telegram_token_set=check_telegram_token(agent.agent_id),
    )


@app.get("/")
def serve_frontend():
    return FileResponse("frontend/index.html")


@app.post("/api/agents", status_code=201, response_model=AgentRead)
def create_agent(body: AgentCreate, session: Session = Depends(get_session)):
    if not SLUG_RE.match(body.agent_id):
        raise HTTPException(400, "agent_id must match [a-z0-9-]+")

    existing = session.exec(select(Agent).where(Agent.agent_id == body.agent_id)).first()
    if existing:
        raise HTTPException(409, f"agent_id '{body.agent_id}' already exists")

    workspace = str(Path(settings.openclaw_workspaces_dir) / body.agent_id)

    try:
        add_agent_to_config(body.agent_id, workspace, body.model_primary)
    except ValueError as e:
        raise HTTPException(409, str(e))

    agent = Agent(
        agent_id=body.agent_id,
        display_name=body.display_name,
        owner_name=body.owner_name,
        organization=body.organization,
        description=body.description,
        model_primary=body.model_primary,
        workspace=workspace,
    )
    session.add(agent)
    session.commit()
    session.refresh(agent)
    return _agent_to_read(agent)


@app.get("/api/agents", response_model=list[AgentRead])
def list_agents(session: Session = Depends(get_session)):
    agents = session.exec(select(Agent)).all()
    return [_agent_to_read(a) for a in agents]


@app.get("/api/agents/{agent_db_id}", response_model=AgentRead)
def get_agent(agent_db_id: str, session: Session = Depends(get_session)):
    agent = session.get(Agent, agent_db_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    return _agent_to_read(agent)


@app.delete("/api/agents/{agent_db_id}")
def delete_agent(agent_db_id: str, session: Session = Depends(get_session)):
    agent = session.get(Agent, agent_db_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    try:
        remove_agent_from_config(agent.agent_id)
    except ValueError:
        pass  # Already missing from config — still soft-delete in DB
    agent.status = "deleted"
    session.add(agent)
    session.commit()
    return {"ok": True, "agent_id": agent.agent_id}


@app.get("/api/openclaw/status")
def openclaw_status():
    return get_openclaw_status()


@app.post("/api/openclaw/reload")
def openclaw_reload():
    try:
        config = load_config()
        save_config(config)
        return {"ok": True, "message": "Reload triggered"}
    except Exception as e:
        raise HTTPException(500, str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=settings.platform_port, reload=True)
