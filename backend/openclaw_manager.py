import json
import os
import subprocess
import tempfile
from pathlib import Path


def _config_path() -> Path:
    return Path(os.environ.get("OPENCLAW_CONFIG_PATH", str(Path.home() / ".openclaw/openclaw.json")))


def load_config() -> dict:
    path = _config_path()
    if not path.exists():
        raise FileNotFoundError(f"openclaw.json not found at {path}")
    with open(path) as f:
        return json.load(f)


def save_config(data: dict) -> None:
    path = _config_path()
    dir_ = str(path.parent)
    with tempfile.NamedTemporaryFile("w", dir=dir_, delete=False, suffix=".tmp") as f:
        json.dump(data, f, indent=2)
        tmp = f.name
    os.replace(tmp, str(path))


def _slug_to_env_var(agent_id: str) -> str:
    return "AGENT_BOT_TOKEN_" + agent_id.upper().replace("-", "_")


def add_agent_to_config(
    agent_id: str,
    workspace: str,
    model_primary: str = "google/gemini-2.5-flash-lite",
) -> None:
    workspace = os.path.expanduser(workspace)
    config = load_config()

    # Ensure nested keys exist
    config.setdefault("agents", {}).setdefault("list", [])
    config.setdefault("channels", {}).setdefault("telegram", {}).setdefault("accounts", {})
    config.setdefault("bindings", [])

    if any(a.get("id") == agent_id for a in config["agents"]["list"]):
        raise ValueError(f"agent_id '{agent_id}' already exists in openclaw.json")

    os.makedirs(workspace, exist_ok=True)

    config["agents"]["list"].append({
        "id": agent_id,
        "workspace": workspace,
        "model": {"primary": model_primary},
    })
    config["channels"]["telegram"]["accounts"][agent_id] = {
        "botToken": "${" + _slug_to_env_var(agent_id) + "}"
    }
    config["bindings"].append({
        "agentId": agent_id,
        "match": {"channel": "telegram", "accountId": agent_id},
    })

    save_config(config)


def remove_agent_from_config(agent_id: str) -> None:
    config = load_config()

    agents_list = config.get("agents", {}).get("list", [])
    if not any(a.get("id") == agent_id for a in agents_list):
        raise ValueError(f"agent_id '{agent_id}' not found in openclaw.json")

    config["agents"]["list"] = [a for a in agents_list if a.get("id") != agent_id]

    accounts = config.get("channels", {}).get("telegram", {}).get("accounts", {})
    accounts.pop(agent_id, None)

    config["bindings"] = [
        b for b in config.get("bindings", []) if b.get("agentId") != agent_id
    ]

    save_config(config)


def get_openclaw_pid() -> int | None:
    result = subprocess.run(["pgrep", "-f", "openclaw"], capture_output=True, text=True)
    if result.returncode == 0:
        pids = result.stdout.strip().split()
        if pids:
            return int(pids[0])
    return None


def get_openclaw_status() -> dict:
    pid = get_openclaw_pid()
    return {
        "alive": pid is not None,
        "pid": pid,
        "gateway_url": os.environ.get("OPENCLAW_GATEWAY_URL", "http://localhost:18789"),
    }


def check_telegram_token(agent_id: str) -> bool:
    env_var = _slug_to_env_var(agent_id)
    value = os.environ.get(env_var, "")
    return bool(value)
