"""
Configuration — Load and merge config from YAML files.

Looks for `config.yaml` in the project root.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def load_config(project_root: str | Path | None = None) -> dict[str, Any]:
    """
    Load configuration from config.yaml in the project root.

    Args:
        project_root: Path to the project root. Defaults to cwd.

    Returns:
        Merged configuration dict.
    """
    import yaml

    if project_root is None:
        project_root = Path.cwd()
    else:
        project_root = Path(project_root)

    config_path = project_root / "config.yaml"

    if not config_path.exists():
        return _defaults()

    with open(config_path, "r", encoding="utf-8") as f:
        user_config = yaml.safe_load(f) or {}

    # Merge user config onto defaults
    defaults = _defaults()
    _deep_merge(defaults, user_config)
    return defaults


def _defaults() -> dict[str, Any]:
    """Return the default configuration."""
    return {
        "bridge": {
            "poll_interval_seconds": 3,
            "max_concurrent_tasks": 1,
            "task_timeout_seconds": 300,
            "agent_bridge_dir": ".agent_bridge",
        },
        "runners": {
            "default": "copilot-cli",
            "copilot_cli": {
                "command": "copilot",
                "model": "gpt-5-mini",
                "allow_all_tools": True,
                "extra_args": [],
            },
        },
        "project": {
            "root": ".",
        },
    }


def _deep_merge(base: dict, override: dict) -> None:
    """Recursively merge `override` into `base` in place."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
