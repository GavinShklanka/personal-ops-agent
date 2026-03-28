"""Basic tests for Klara's configuration loading."""

import pytest
from pathlib import Path


def test_config_exists():
    config_path = Path(__file__).parent.parent / "config" / "settings.yaml"
    assert config_path.exists(), "settings.yaml not found"


def test_config_loads():
    import yaml
    config_path = Path(__file__).parent.parent / "config" / "settings.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)
    assert "klara" in config
    assert "name" in config["klara"]
    assert config["klara"]["name"] == "Klara"


def test_env_example_exists():
    env_example = Path(__file__).parent.parent / ".env.example"
    assert env_example.exists(), ".env.example not found"
