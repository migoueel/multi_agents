"""
Configuration — Load and merge config from YAML files.

Looks for `config.yaml` in the project root.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional


def load_config(project_root: str | Path | None = None, fail_on_error: Optional[bool] = None) -> dict[str, Any]:
    """
    Load configuration from config.yaml in the project root.

    Args:
        project_root: Path to the project root. Defaults to cwd.

    Returns:
        Merged configuration dict.
    """
    import yaml
    import sys
    import inspect

    if fail_on_error is None:
        fail_on_error = any(
            "agent_maestro\\cli.py" in (frame.filename or "")
            for frame in inspect.stack()
        )

    if project_root is None:
        project_root = Path.cwd()
    else:
        project_root = Path(project_root)

    config_path = project_root / "config.yaml"

    if not config_path.exists():
        return _defaults()

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            try:
                user_config = yaml.safe_load(f) or {}
            except yaml.YAMLError as e:
                msg = f"Failed to parse config.yaml: {e}"
                # decide whether to fail or fallback based on caller context
                if fail_on_error:
                    print(msg, file=sys.stderr)
                    raise SystemExit(2)
                else:
                    print(f"Warning: {msg}; using defaults.", file=sys.stderr)
                    return _defaults()
    except OSError as e:
        msg = f"Unable to read config.yaml: {e}"
        if fail_on_error:
            print(msg, file=sys.stderr)
            raise SystemExit(2)
        else:
            print(f"Warning: {msg}; using defaults.", file=sys.stderr)
            return _defaults()

    # Merge user config onto defaults
    defaults = _defaults()
    _deep_merge(defaults, user_config)

    # Normalize runners default key (allow hyphen/underscore mismatch)
    runners = defaults.get("runners", {})
    default_runner = runners.get("default")
    if default_runner and default_runner not in runners:
        alt = default_runner.replace("-", "_")
        alt2 = default_runner.replace("_", "-")
        if alt in runners:
            runners["default"] = alt
        elif alt2 in runners:
            runners["default"] = alt2
        else:
            msg = (
                f"Configured default runner '{default_runner}' not found in runners: "
                f"{list(runners.keys())}"
            )
            if fail_on_error:
                print(msg, file=sys.stderr)
                raise SystemExit(2)
            else:
                raise ValueError(msg)

    # Basic type validation / coercion for bridge settings
    bridge = defaults.get("bridge", {})
    def _handle_error(msg: str):
        if fail_on_error:
            print(msg, file=sys.stderr)
            raise SystemExit(2)
        # non-CLI callers get an exception
        raise ValueError(msg)

    for key in ("poll_interval_seconds", "max_concurrent_tasks"):
        val = bridge.get(key)
        if isinstance(val, str):
            if val.isdigit():
                bridge[key] = int(val)
            else:
                _handle_error(
                    f"Invalid value for bridge.{key}: expected integer, got '{val}'"
                )
        elif not isinstance(val, int):
            _handle_error(
                f"Invalid type for bridge.{key}: expected int, got {type(val).__name__}"
            )

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
                "allow_all_paths": True,
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
