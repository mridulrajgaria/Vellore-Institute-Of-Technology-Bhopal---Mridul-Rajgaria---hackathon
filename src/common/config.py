"""Configuration loader utilities."""

from pathlib import Path
from typing import Any, Dict
import yaml


def load_yaml(path: str | Path) -> Dict[str, Any]:
    """Load a YAML configuration file safely."""
    config_path = Path(path)
    if not config_path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_default_config(path: str | Path = "config/default.yaml") -> Dict[str, Any]:
    """Load default application parameters."""
    return load_yaml(path)


def load_companies_config(path: str | Path = "config/companies.yaml") -> Dict[str, Any]:
    """Load ticker-to-company name mapping and aliases."""
    return load_yaml(path)


def load_engine_config(path: str | Path = "config/engine.yaml") -> Dict[str, Any]:
    """Load risk engine event classification and impact scoring configuration."""
    return load_yaml(path)

