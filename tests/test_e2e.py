"""
End-to-end smoke test — Full lifecycle with a mock runner.

Tests the watcher picking up a pending task, dispatching it through
a mock runner (no actual Copilot invocation), and recording the result.
"""

import threading
import time

import pytest

from agent_maestro.protocol import Task, TaskStatus, RunResult
from agent_maestro.queue import TaskQueue
from agent_maestro.runners.base import BaseRunner
from agent_maestro.watcher import BridgeWatcher


class MockRunner(BaseRunner):
    """A runner that immediately succeeds with a canned response."""

    def __init__(self, delay: float = 0.1, should_fail: bool = False):
        self.delay = delay
        self.should_fail = should_fail
        self.executed_tasks: list[str] = []

    def execute(self, task: Task, project_root: str) -> RunResult:
        time.sleep(self.delay)
        self.executed_tasks.append(task.id)

        if self.should_fail:
            return RunResult(success=False, error="Mock failure")
        return RunResult(
            success=True,
            output=f"Mock completed: {task.instructions}",
            files_modified=task.target_files,
        )


@pytest.fixture
def setup(tmp_path):
    """Set up a queue, mock runner, and watcher."""
    queue = TaskQueue(tmp_path / ".agent_bridge")
    runner = MockRunner(delay=0.05)
    watcher = BridgeWatcher(
        queue=queue,
        project_root=str(tmp_path),
        runner=runner,
        poll_interval=0.2,
        max_workers=1,
    )
    return queue, runner, watcher


class TestEndToEnd:
    def test_task_completes_via_watcher(self, setup):
        queue, runner, watcher = setup

        task = queue.create_task(
            instructions="Write a hello world function",
            target_files=["src/hello.py"],
        )

        thread = threading.Thread(target=watcher.start, daemon=True)
        thread.start()

        for _ in range(50):
            result = queue.get_task(task.id)
            if result and result.status == TaskStatus.COMPLETED:
                break
            time.sleep(0.1)

        watcher.stop()
        thread.join(timeout=3)

        final = queue.get_task(task.id)
        assert final is not None
        assert final.status == TaskStatus.COMPLETED
        assert "Mock completed" in final.result
        assert task.id in runner.executed_tasks

    def test_failed_task_recorded(self, tmp_path):
        queue = TaskQueue(tmp_path / ".agent_bridge")
        runner = MockRunner(delay=0.05, should_fail=True)
        watcher = BridgeWatcher(
            queue=queue,
            project_root=str(tmp_path),
            runner=runner,
            poll_interval=0.2,
        )

        task = queue.create_task(instructions="This will fail")

        thread = threading.Thread(target=watcher.start, daemon=True)
        thread.start()

        for _ in range(50):
            result = queue.get_task(task.id)
            if result and result.status == TaskStatus.FAILED:
                break
            time.sleep(0.1)

        watcher.stop()
        thread.join(timeout=3)

        final = queue.get_task(task.id)
        assert final is not None
        assert final.status == TaskStatus.FAILED
        assert "Mock failure" in final.error

    def test_priority_ordering_processed_first(self, setup):
        queue, runner, watcher = setup

        low = queue.create_task(instructions="Low priority work", priority=0)
        high = queue.create_task(instructions="Urgent work", priority=10)

        thread = threading.Thread(target=watcher.start, daemon=True)
        thread.start()

        for _ in range(100):
            tasks = queue.list_tasks(status=TaskStatus.COMPLETED)
            if len(tasks) >= 2:
                break
            time.sleep(0.1)

        watcher.stop()
        thread.join(timeout=3)

        assert runner.executed_tasks[0] == high.id
        assert runner.executed_tasks[1] == low.id

    def test_task_with_agent_type(self, setup):
        """Verify agent_type is preserved through the full lifecycle."""
        queue, runner, watcher = setup

        task = queue.create_task(
            instructions="Write tests for utils.py",
            agent_type="tester",
        )

        thread = threading.Thread(target=watcher.start, daemon=True)
        thread.start()

        for _ in range(50):
            result = queue.get_task(task.id)
            if result and result.status == TaskStatus.COMPLETED:
                break
            time.sleep(0.1)

        watcher.stop()
        thread.join(timeout=3)

        final = queue.get_task(task.id)
        assert final is not None
        assert final.status == TaskStatus.COMPLETED
        assert final.agent_type == "tester"
