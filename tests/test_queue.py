"""
Tests for agent_maestro.queue — File-based task queue operations.
"""

import tempfile
from pathlib import Path

import pytest

from agent_maestro.protocol import Task, TaskStatus
from agent_maestro.queue import TaskQueue


@pytest.fixture
def queue(tmp_path):
    """Create a TaskQueue in a temporary directory."""
    return TaskQueue(tmp_path / ".agent_bridge")


class TestQueueCreation:
    def test_creates_subdirectories(self, queue):
        assert (queue.root / "pending").is_dir()
        assert (queue.root / "running").is_dir()
        assert (queue.root / "completed").is_dir()
        assert (queue.root / "failed").is_dir()

    def test_create_task(self, queue):
        task = queue.create_task(
            instructions="Write tests",
            target_files=["src/utils.py"],
        )
        assert task.status == TaskStatus.PENDING
        assert (queue.root / "pending" / task.filename).exists()

    def test_create_task_with_all_fields(self, queue):
        task = queue.create_task(
            instructions="Refactor module",
            agent="copilot",
            action="refactor",
            target_files=["src/auth.py"],
            context="Keep backward compat",
            priority=3,
        )
        assert task.agent == "copilot"
        assert task.priority == 3

    def test_create_task_with_agent_type(self, queue):
        task = queue.create_task(
            instructions="Implement feature",
            agent_type="implementer",
        )
        assert task.agent_type == "implementer"
        loaded = queue.get_task(task.id)
        assert loaded.agent_type == "implementer"


class TestQueueOperations:
    def test_get_task(self, queue):
        task = queue.create_task(instructions="Test")
        found = queue.get_task(task.id)
        assert found is not None
        assert found.id == task.id

    def test_get_task_not_found(self, queue):
        assert queue.get_task("nonexistent") is None

    def test_claim_task(self, queue):
        task = queue.create_task(instructions="Test")
        claimed = queue.claim_task(task.id)
        assert claimed.status == TaskStatus.RUNNING
        assert not (queue.root / "pending" / task.filename).exists()
        assert (queue.root / "running" / task.filename).exists()

    def test_claim_non_pending_raises(self, queue):
        task = queue.create_task(instructions="Test")
        queue.claim_task(task.id)
        with pytest.raises(ValueError, match="expected PENDING"):
            queue.claim_task(task.id)

    def test_complete_task(self, queue):
        task = queue.create_task(instructions="Test")
        queue.claim_task(task.id)
        completed = queue.complete_task(task.id, "All done")
        assert completed.status == TaskStatus.COMPLETED
        assert completed.result == "All done"
        assert (queue.root / "completed" / task.filename).exists()

    def test_fail_task(self, queue):
        task = queue.create_task(instructions="Test")
        queue.claim_task(task.id)
        failed = queue.fail_task(task.id, "Timeout")
        assert failed.status == TaskStatus.FAILED
        assert failed.error == "Timeout"
        assert (queue.root / "failed" / task.filename).exists()


class TestQueueQueries:
    def test_list_all_tasks(self, queue):
        queue.create_task(instructions="Task 1")
        queue.create_task(instructions="Task 2")
        t3 = queue.create_task(instructions="Task 3")
        queue.claim_task(t3.id)

        all_tasks = queue.list_tasks()
        assert len(all_tasks) == 3

    def test_list_by_status(self, queue):
        queue.create_task(instructions="Pending 1")
        queue.create_task(instructions="Pending 2")
        t = queue.create_task(instructions="Will run")
        queue.claim_task(t.id)

        pending = queue.list_tasks(status=TaskStatus.PENDING)
        assert len(pending) == 2
        running = queue.list_tasks(status=TaskStatus.RUNNING)
        assert len(running) == 1

    def test_priority_ordering(self, queue):
        queue.create_task(instructions="Low priority", priority=0)
        queue.create_task(instructions="High priority", priority=10)
        queue.create_task(instructions="Medium priority", priority=5)

        pending = queue.get_pending_tasks()
        assert pending[0].priority == 10
        assert pending[1].priority == 5
        assert pending[2].priority == 0

    def test_stats(self, queue):
        queue.create_task(instructions="P1")
        queue.create_task(instructions="P2")
        t = queue.create_task(instructions="R1")
        queue.claim_task(t.id)

        stats = queue.stats()
        assert stats["PENDING"] == 2
        assert stats["RUNNING"] == 1
        assert stats["COMPLETED"] == 0
        assert stats["FAILED"] == 0


class TestQueueCleanup:
    def test_clear_completed(self, queue):
        t = queue.create_task(instructions="Test")
        queue.claim_task(t.id)
        queue.complete_task(t.id, "Done")

        assert queue.clear_completed() == 1
        assert queue.stats()["COMPLETED"] == 0

    def test_clear_failed(self, queue):
        t = queue.create_task(instructions="Test")
        queue.claim_task(t.id)
        queue.fail_task(t.id, "Error")

        assert queue.clear_failed() == 1
        assert queue.stats()["FAILED"] == 0
