import tempfile
import subprocess
import shutil
from pathlib import Path
from agent_maestro.runners.copilot_runner import CopilotRunner
from agent_maestro.protocol import Task


def test_no_mktemp_and_uses_argv(monkeypatch, tmp_path):
    # Fail if tempfile.mktemp is used
    def mktemp_fail(*args, **kwargs):
        raise AssertionError("tempfile.mktemp should not be used")

    monkeypatch.setattr(tempfile, "mktemp", mktemp_fail)

    # Ensure which finds a fake copilot executable
    monkeypatch.setattr(shutil, "which", lambda cmd: str(Path(sys_executable := __import__('sys').executable)))

    captured = {}

    class DummyPopen:
        def __init__(self, cmd, stdout, stderr, cwd=None):
            # capture the cmd for assertions
            captured['cmd'] = cmd
            # ensure we received a list and not a single PowerShell -Command string
            assert isinstance(cmd, list)
            flat = " ".join(str(x) for x in cmd).lower()
            assert 'powershell' not in flat
            # write output to the file-like stdout
            try:
                stdout.write(b"ok\n")
                stdout.flush()
            except Exception:
                pass
            self.returncode = 0

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(subprocess, "Popen", DummyPopen)

    runner = CopilotRunner()
    task = Task(instructions="Do something safe")
    res = runner.execute(task, project_root=str(tmp_path))
    assert res.success
    assert 'ok' in res.output.lower()
    # Inspect captured cmd
    assert '-p' in captured['cmd']


def test_extra_args_sanitization(monkeypatch, tmp_path):
    # Allow safe args, reject dangerous ones
    monkeypatch.setattr(shutil, "which", lambda cmd: str(__import__('sys').executable))

    seen_cmd = {}

    class DummyPopen2:
        def __init__(self, cmd, stdout, stderr, cwd=None):
            seen_cmd['cmd'] = cmd
            self.returncode = 0
            try:
                stdout.write(b"ok2\n")
                stdout.flush()
            except Exception:
                pass

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(subprocess, "Popen", DummyPopen2)

    runner = CopilotRunner(extra_args=['--quiet', 'value'])
    task = Task(instructions="Test extra args")
    res = runner.execute(task, project_root=str(tmp_path))
    assert res.success
    assert '--quiet' in seen_cmd['cmd']

    # Now try a dangerous arg
    runner2 = CopilotRunner(extra_args=['; rm -rf /'])
    res2 = runner2.execute(task, project_root=str(tmp_path))
    assert not res2.success
    assert 'Invalid extra arg' in res2.error
