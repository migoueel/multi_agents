"""
Run with: pytest -q tests/test_queue_concurrency.py::test_concurrent_claims

This test creates a single pending task and launches two separate Python
processes (via the helper script) that both attempt to claim the same task.
Exactly one process must succeed and the other must report "ALREADY".
"""
import sys
import subprocess
from pathlib import Path

from agent_maestro.queue import TaskQueue


def test_concurrent_claims(tmp_path):
    root = tmp_path / ".agent_bridge"
    q = TaskQueue(root)

    # Create a single pending task
    task = q.create_task("Perform concurrent claim test")

    script = Path(__file__).parent / "claim_worker.py"
    assert script.exists(), f"helper script not found: {script}"

    # Launch two independent Python processes that attempt to claim the task
    p1 = subprocess.Popen([sys.executable, str(script), str(root), task.id], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    p2 = subprocess.Popen([sys.executable, str(script), str(root), task.id], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    out1, err1 = p1.communicate(timeout=10)
    out2, err2 = p2.communicate(timeout=10)

    results = []
    for out, err, rc in ((out1, err1, p1.returncode), (out2, err2, p2.returncode)):
        out = (out or "").strip()
        err = (err or "").strip()
        if "SUCCESS" in out or rc == 0:
            results.append("success")
        elif "ALREADY" in out or "expected PENDING" in out or "expected PENDING" in err:
            results.append("already")
        else:
            results.append("error")

    assert results.count("success") == 1, f"Expected exactly one success, got: {results} (stdout1={out1!r}, stderr1={err1!r}, stdout2={out2!r}, stderr2={err2!r})"
    assert results.count("already") == 1, f"Expected one 'already' response, got: {results}"