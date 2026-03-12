from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openclaw_config_path: str = str(Path.home() / ".openclaw/openclaw.json")
    openclaw_workspaces_dir: str = str(Path.home() / ".openclaw/workspaces")
    openclaw_gateway_url: str = "http://localhost:18789"
    openclaw_gateway_token: str = ""
    platform_port: int = 3000
    database_url: str = "sqlite:///./agents.db"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
