"""
Tests for agent_maestro.protocol — Task schema and serialization.
"""

import json
import tempfile
from pathlib import Path

from agent_maestro.protocol import Task, TaskStatus, TaskAction, RunResult


class TestTaskStatus:
    def test_status_values(self):
        assert TaskStatus.PENDING.value == "PENDING"
        assert TaskStatus.RUNNING.value == "RUNNING"
        assert TaskStatus.COMPLETED.value == "COMPLETED"
        assert TaskStatus.FAILED.value == "FAILED"


class TestTask:
    def test_create_minimal(self):
        task = Task(instructions="Do something")
        assert task.instructions == "Do something"
        assert task.agent == "gpt-5-mini"
        assert task.action == "implement"
        assert task.status == TaskStatus.PENDING
        assert task.result is None
        assert task.error is None
        assert len(task.id) == 8

    def test_create_full(self):
        task = Task(
            instructions="Write tests",
            agent="copilot",
            action="test",
            target_files=["src/utils.py"],
            context="Use pytest",
            priority=5,
        )
        assert task.agent == "copilot"
        assert task.action == "test"
        assert task.target_files == ["src/utils.py"]
        assert task.priority == 5

    def test_agent_type_field(self):
        task = Task(
            instructions="Implement feature",
            agent_type="implementer",
        )
        assert task.agent_type == "implementer"
        assert "@implementer" in str(task)

    def test_agent_type_default_empty(self):
        task = Task(instructions="Do something")
        assert task.agent_type == ""

    def test_serialization_roundtrip(self):
        task = Task(
            instructions="Refactor auth module",
            target_files=["src/auth.py", "src/tokens.py"],
            action="refactor",
            context="Keep backward compat",
            agent_type="implementer",
        )
        json_str = task.to_json()
        restored = Task.from_json(json_str)

        assert restored.id == task.id
        assert restored.instructions == task.instructions
        assert restored.target_files == task.target_files
        assert restored.status == TaskStatus.PENDING
        assert restored.context == task.context
        assert restored.agent_type == "implementer"

    def test_dict_roundtrip(self):
        task = Task(instructions="Fix bug #42")
        d = task.to_dict()
        assert isinstance(d, dict)
        assert d["status"] == "PENDING"

        restored = Task.from_dict(d)
        assert restored.id == task.id
        assert restored.status == TaskStatus.PENDING

    def test_legacy_dict_without_agent_type(self):
        """Tasks created before agent_type was added should still load."""
        legacy_data = {
            "instructions": "Old task",
            "agent": "gpt-5-mini",
            "action": "implement",
            "target_files": [],
            "status": "PENDING",
            "context": "",
            "result": None,
            "error": None,
            "id": "legacy01",
            "created_at": "2026-01-01T00:00:00+00:00",
            "completed_at": None,
            "priority": 0,
        }
        task = Task.from_dict(legacy_data)
        assert task.agent_type == ""
        assert task.id == "legacy01"

    def test_file_roundtrip(self):
        task = Task(instructions="Document the API")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / task.filename
            task.save(path)

            loaded = Task.from_file(path)
            assert loaded.id == task.id
            assert loaded.instructions == task.instructions

    def test_mark_running(self):
        task = Task(instructions="Test")
        task.mark_running()
        assert task.status == TaskStatus.RUNNING

    def test_mark_completed(self):
        task = Task(instructions="Test")
        task.mark_completed("All done")
        assert task.status == TaskStatus.COMPLETED
        assert task.result == "All done"
        assert task.completed_at is not None

    def test_mark_failed(self):
        task = Task(instructions="Test")
        task.mark_failed("Something broke")
        assert task.status == TaskStatus.FAILED
        assert task.error == "Something broke"
        assert task.completed_at is not None

    def test_filename(self):
        task = Task(instructions="Test", id="abc12345")
        assert task.filename == "task_abc12345.json"

    def test_str_representation(self):
        task = Task(instructions="Write a hello world function")
        s = str(task)
        assert "⏳" in s
        assert task.id in s


class TestRunResult:
    def test_success(self):
        r = RunResult(success=True, output="Done")
        assert r.success is True
        assert r.output == "Done"
        assert r.error == ""

    def test_failure(self):
        r = RunResult(success=False, error="Timeout")
        assert r.success is False
        assert r.error == "Timeout"
