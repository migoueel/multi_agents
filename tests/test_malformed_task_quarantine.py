"""
Test that a malformed task JSON in .agent_bridge/pending is quarantined when listing tasks.

This test writes an intentionally-malformed JSON file into the pending directory
and invokes TaskQueue.list_tasks(). The expected behavior (for the implementer
changes) is that malformed files are moved to .agent_bridge/quarantine/ and a
warning is logged.

NOTE: The current implementation of list_tasks() silently skips malformed files
without moving them; this test encodes the desired behavior and will be used by
an implementer task that updates production code accordingly.
"""
import logging
from pathlib import Path

from agent_maestro.queue import TaskQueue


def test_malformed_task_quarantine(tmp_path, caplog):
    root = tmp_path / ".agent_bridge"
    q = TaskQueue(root)

    # Ensure pending exists and drop a malformed JSON file into it
    pending = root / "pending"
    pending.mkdir(parents=True, exist_ok=True)
    bad = pending / "task_malformed.json"
    bad.write_text("{ this is not: valid json", encoding="utf-8")

    caplog.set_level(logging.WARNING)

    # Call the API that should detect and quarantine malformed tasks
    tasks = q.list_tasks()

    # After the desired behavior is implemented the malformed file should be moved
    quarantine = root / "quarantine"
    assert (quarantine / "task_malformed.json").exists(), "Malformed task should be moved to quarantine"

    # And a warning should have been emitted
    assert any("malform" in rec.message.lower() or "quarantine" in rec.message.lower() for rec in caplog.records), "Expected a warning about malformed task"