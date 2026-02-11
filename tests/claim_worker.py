#!/usr/bin/env python
"""Helper script used by tests/test_queue_concurrency.py.

Usage: python claim_worker.py <root_path> <task_id>

Attempts to claim the given task in the file-based queue and prints one of:
 - SUCCESS  (exit 0)
 - ALREADY  (exit 2)  -> task already claimed or not in PENDING
 - ERROR    (exit 3)  -> unexpected error
"""
import sys
import traceback
from pathlib import Path


def main(argv):
    if len(argv) < 3:
        print("USAGE: claim_worker.py <root_path> <task_id>")
        return 3
    root = Path(argv[1])
    task_id = argv[2]

    # Import here so the script can be executed as a separate process
    try:
        from agent_maestro.queue import TaskQueue
    except Exception as e:
        print("ERROR importing TaskQueue:", e)
        traceback.print_exc()
        return 3

    try:
        q = TaskQueue(root)
        q.claim_task(task_id)
        print("SUCCESS")
        return 0
    except ValueError as e:
        # Expected path when another process already claimed the task
        print("ALREADY", str(e))
        return 2
    except Exception as e:
        print("ERROR", str(e))
        traceback.print_exc()
        return 3


if __name__ == "__main__":
    rc = main(sys.argv)
    sys.exit(rc)
