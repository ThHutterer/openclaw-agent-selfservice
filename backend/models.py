import uuid
from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


class Agent(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    agent_id: str = Field(unique=True, index=True)
    display_name: str
    owner_name: str
    organization: str
    description: str
    model_primary: str = "google/gemini-2.5-flash-lite"
    workspace: str
    status: str = "active"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AgentCreate(SQLModel):
    agent_id: str
    display_name: str
    owner_name: str
    organization: str
    description: str
    model_primary: str = "google/gemini-2.5-flash-lite"


class AgentRead(SQLModel):
    id: str
    agent_id: str
    display_name: str
    owner_name: str
    organization: str
    description: str
    model_primary: str
    workspace: str
    status: str
    created_at: datetime
    telegram_token_set: bool
