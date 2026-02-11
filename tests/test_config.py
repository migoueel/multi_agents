import textwrap
from pathlib import Path

import pytest

from agent_maestro.config import load_config


def write_config(path: Path, content: str):
    path.write_text(textwrap.dedent(content), encoding="utf-8")


def test_malformed_yaml_fallback(tmp_path, capsys):
    cfg_file = tmp_path / "config.yaml"
    # Intentionally malformed YAML
    write_config(cfg_file, """
    bad: [unclosed
    """)

    cfg = load_config(tmp_path)
    assert isinstance(cfg, dict)
    assert "bridge" in cfg

    captured = capsys.readouterr()
    assert "Failed to parse" in captured.err or "Warning" in captured.err


def test_malformed_yaml_fail_fast(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    write_config(cfg_file, """
    bad: [unclosed
    """)

    with pytest.raises(SystemExit):
        load_config(tmp_path, fail_on_error=True)


def test_runner_default_normalization(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    write_config(cfg_file, """
    runners:
      default: copilot-cli
      copilot_cli:
        command: copilot
    """)

    cfg = load_config(tmp_path)
    assert cfg["runners"]["default"] == "copilot_cli"
