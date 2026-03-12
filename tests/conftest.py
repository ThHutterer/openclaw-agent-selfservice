import json
import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def tmp_openclaw_config(tmp_path_factory):
    """Create a temporary openclaw.json for tests."""
    config_dir = tmp_path_factory.mktemp("openclaw")
    config_path = config_dir / "openclaw.json"
    config_path.write_text(json.dumps({
        "agents": {"defaults": {"sandbox": {}}, "list": []},
        "channels": {"telegram": {"accounts": {}}},
        "bindings": []
    }, indent=2))
    os.environ["OPENCLAW_CONFIG_PATH"] = str(config_path)
    os.environ["OPENCLAW_WORKSPACES_DIR"] = str(config_dir / "workspaces")
    (config_dir / "workspaces").mkdir(exist_ok=True)
    return config_path


@pytest.fixture(scope="session")
def client(tmp_openclaw_config):
    from backend.main import app
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c
