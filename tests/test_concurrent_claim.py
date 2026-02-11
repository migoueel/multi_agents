import sys
import subprocess
from pathlib import Path
from agent_maestro.queue import TaskQueue


def test_concurrent_claim(tmp_path):
    # Setup queue in temporary directory
    root = tmp_path / "agent_bridge"
    q = TaskQueue(root)
    task = q.create_task(instructions="race-condition test")
    task_id = task.id

    # Write a small worker script that attempts to claim the task
    worker = tmp_path / "claim_worker.py"
    worker.write_text(
        """
import sys
from pathlib import Path
from agent_maestro.queue import TaskQueue

root = Path(sys.argv[1])
taskid = sys.argv[2]
q = TaskQueue(root)
try:
    q.claim_task(taskid)
    print('OK')
    sys.exit(0)
except Exception as e:
    print('ERR', e)
    sys.exit(1)
""",
        encoding="utf-8",
    )

    # Launch two subprocesses concurrently
    p1 = subprocess.Popen([sys.executable, str(worker), str(root), task_id], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    p2 = subprocess.Popen([sys.executable, str(worker), str(root), task_id], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    out1, err1 = p1.communicate(timeout=10)
    out2, err2 = p2.communicate(timeout=10)

    ok1 = out1.decode().strip().startswith("OK")
    ok2 = out2.decode().strip().startswith("OK")

    # Exactly one process should have succeeded
    assert (1 == sum([1 for ok in (ok1, ok2) if ok]))

    # Check that there is exactly one file in running/
    running_files = list((root / "running").glob("task_*.json"))
    assert len(running_files) == 1
