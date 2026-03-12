import json
import os

import pytest


def test_add_and_remove_agent(tmp_path):
    config_path = tmp_path / "openclaw.json"
    config_path.write_text(json.dumps({
        "agents": {"defaults": {}, "list": []},
        "channels": {"telegram": {"accounts": {}}},
        "bindings": [],
    }))
    workspaces = tmp_path / "workspaces"
    workspaces.mkdir()

    os.environ["OPENCLAW_CONFIG_PATH"] = str(config_path)
    os.environ["OPENCLAW_WORKSPACES_DIR"] = str(workspaces)

    from backend.openclaw_manager import add_agent_to_config, load_config, remove_agent_from_config

    add_agent_to_config("test-unit", str(workspaces / "test-unit"))
    config = load_config()
    assert any(a["id"] == "test-unit" for a in config["agents"]["list"])
    assert "test-unit" in config["channels"]["telegram"]["accounts"]
    assert any(b["agentId"] == "test-unit" for b in config["bindings"])

    account = config["channels"]["telegram"]["accounts"]["test-unit"]
    assert account["botToken"] == "${AGENT_BOT_TOKEN_TEST_UNIT}"

    with pytest.raises(ValueError):
        add_agent_to_config("test-unit", str(workspaces / "test-unit"))

    remove_agent_from_config("test-unit")
    config = load_config()
    assert not any(a["id"] == "test-unit" for a in config["agents"]["list"])
    assert "test-unit" not in config["channels"]["telegram"]["accounts"]
    assert not any(b["agentId"] == "test-unit" for b in config["bindings"])


def test_remove_nonexistent_raises(tmp_path):
    config_path = tmp_path / "openclaw.json"
    config_path.write_text(json.dumps({
        "agents": {"list": []},
        "channels": {"telegram": {"accounts": {}}},
        "bindings": [],
    }))
    os.environ["OPENCLAW_CONFIG_PATH"] = str(config_path)

    from backend.openclaw_manager import remove_agent_from_config
    with pytest.raises(ValueError):
        remove_agent_from_config("nonexistent")


def test_slug_to_env_var():
    from backend.openclaw_manager import _slug_to_env_var
    assert _slug_to_env_var("my-rag-agent") == "AGENT_BOT_TOKEN_MY_RAG_AGENT"
    assert _slug_to_env_var("simple") == "AGENT_BOT_TOKEN_SIMPLE"
    assert _slug_to_env_var("a-b-c") == "AGENT_BOT_TOKEN_A_B_C"


def test_check_telegram_token(monkeypatch, tmp_path):
    config_path = tmp_path / "openclaw.json"
    config_path.write_text(json.dumps({
        "agents": {"list": []},
        "channels": {"telegram": {"accounts": {}}},
        "bindings": [],
    }))
    os.environ["OPENCLAW_CONFIG_PATH"] = str(config_path)

    from backend.openclaw_manager import check_telegram_token

    monkeypatch.setenv("AGENT_BOT_TOKEN_MY_AGENT", "tok123")
    assert check_telegram_token("my-agent") is True

    monkeypatch.delenv("AGENT_BOT_TOKEN_MY_AGENT", raising=False)
    assert check_telegram_token("my-agent") is False


def test_atomic_write(tmp_path):
    config_path = tmp_path / "openclaw.json"
    config_path.write_text(json.dumps({
        "agents": {"list": []},
        "channels": {"telegram": {"accounts": {}}},
        "bindings": [],
    }))
    os.environ["OPENCLAW_CONFIG_PATH"] = str(config_path)

    from backend.openclaw_manager import load_config, save_config

    data = load_config()
    data["test_marker"] = "atomic_write_test"
    save_config(data)

    result = load_config()
    assert result["test_marker"] == "atomic_write_test"

    tmp_files = list(tmp_path.glob("*.tmp"))
    assert len(tmp_files) == 0
