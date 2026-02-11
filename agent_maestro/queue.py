"""
Task Queue — File-based persistent task queue.

Tasks are stored as individual JSON files in status-based subdirectories
under the `.agent_bridge/` root:

    .agent_bridge/
    ├── pending/       # Tasks waiting to be picked up
    ├── running/       # Tasks currently being executed
    ├── completed/     # Finished tasks with results
    └── failed/        # Failed tasks with error info

Moving a task between directories is the atomic status transition.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Optional

from .protocol import Task, TaskStatus


# Map each status to its subdirectory name
_STATUS_DIRS: dict[TaskStatus, str] = {
    TaskStatus.PENDING: "pending",
    TaskStatus.RUNNING: "running",
    TaskStatus.COMPLETED: "completed",
    TaskStatus.FAILED: "failed",
}


class TaskQueue:
    """
    File-based task queue rooted at a given directory.

    Usage:
        queue = TaskQueue(Path(".agent_bridge"))
        task = queue.create_task(instructions="Write unit tests for utils.py")
        queue.claim_task(task.id)        # pending → running
        queue.complete_task(task.id, "Done — 12 tests added.")
    """

    def __init__(self, root: Path | str):
        self.root = Path(root)
        self._ensure_dirs()

    # ── Directory management ─────────────────────────────────────────

    def _ensure_dirs(self) -> None:
        """Create subdirectories if they don't exist."""
        for subdir in _STATUS_DIRS.values():
            (self.root / subdir).mkdir(parents=True, exist_ok=True)

    def _dir_for(self, status: TaskStatus) -> Path:
        return self.root / _STATUS_DIRS[status]

    # ── Core operations ──────────────────────────────────────────────

    def create_task(
        self,
        instructions: str,
        agent: str = "gpt-5-mini",
        action: str = "implement",
        target_files: Optional[list[str]] = None,
        context: str = "",
        priority: int = 0,
        agent_type: str = "",
    ) -> Task:
        """
        Create a new PENDING task and persist it to disk.

        Returns the created Task with its auto-generated ID.
        """
        task = Task(
            instructions=instructions,
            agent=agent,
            action=action,
            target_files=target_files or [],
            context=context,
            priority=priority,
            agent_type=agent_type,
        )
        dest = self._dir_for(TaskStatus.PENDING) / task.filename
        task.save(dest)
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """
        Find a task by ID across all status directories.
        Returns None if not found.
        """
        filename = f"task_{task_id}.json"
        for status_dir in _STATUS_DIRS.values():
            path = self.root / status_dir / filename
            if path.exists():
                return Task.from_file(path)
        return None

    def _find_task_path(self, task_id: str) -> Optional[Path]:
        """Locate the file path for a task by ID."""
        filename = f"task_{task_id}.json"
        for status_dir in _STATUS_DIRS.values():
            path = self.root / status_dir / filename
            if path.exists():
                return path
        return None

    def _move_task(self, task: Task, new_status: TaskStatus) -> Path:
        """
        Move a task file from its current directory to the new status dir.
        Updates the task's status field and re-saves.
        """
        old_path = self._find_task_path(task.id)
        if old_path is None:
            raise FileNotFoundError(f"Task {task.id} not found in queue")

        new_dir = self._dir_for(new_status)
        new_path = new_dir / task.filename
        
        # Update and save to new location, then remove old
        task.save(new_path)
        if old_path != new_path:
            old_path.unlink(missing_ok=True)

        return new_path

    def claim_task(self, task_id: str) -> Task:
        """
        Move a task from PENDING → RUNNING.
        Raises ValueError if the task is not in PENDING state.
        """
        task = self.get_task(task_id)
        if task is None:
            raise ValueError(f"Task {task_id} not found")
        if task.status != TaskStatus.PENDING:
            raise ValueError(
                f"Task {task_id} is {task.status.value}, expected PENDING"
            )
        task.mark_running()
        self._move_task(task, TaskStatus.RUNNING)
        return task

    def complete_task(self, task_id: str, result: str) -> Task:
        """
        Move a task from RUNNING → COMPLETED with a result summary.
        """
        task = self.get_task(task_id)
        if task is None:
            raise ValueError(f"Task {task_id} not found")
        if task.status != TaskStatus.RUNNING:
            raise ValueError(
                f"Task {task_id} is {task.status.value}, expected RUNNING"
            )
        task.mark_completed(result)
        self._move_task(task, TaskStatus.COMPLETED)
        return task

    def fail_task(self, task_id: str, error: str) -> Task:
        """
        Move a task from RUNNING → FAILED with an error message.
        """
        task = self.get_task(task_id)
        if task is None:
            raise ValueError(f"Task {task_id} not found")
        task.mark_failed(error)
        self._move_task(task, TaskStatus.FAILED)
        return task

    # ── Queries ──────────────────────────────────────────────────────

    def list_tasks(self, status: Optional[TaskStatus] = None) -> list[Task]:
        """
        List all tasks, optionally filtered by status.
        Sorted by priority (descending) then creation time (ascending).
        """
        tasks: list[Task] = []
        statuses = [status] if status else list(TaskStatus)

        for s in statuses:
            dir_path = self._dir_for(s)
            for file in dir_path.glob("task_*.json"):
                try:
                    tasks.append(Task.from_file(file))
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue  # Skip malformed task files

        tasks.sort(key=lambda t: (-t.priority, t.created_at))
        return tasks

    def get_pending_tasks(self) -> list[Task]:
        """Get all pending tasks, highest priority first."""
        return self.list_tasks(status=TaskStatus.PENDING)

    def get_running_tasks(self) -> list[Task]:
        """Get all currently running tasks."""
        return self.list_tasks(status=TaskStatus.RUNNING)

    def get_completed_tasks(self) -> list[Task]:
        """Get all completed tasks."""
        return self.list_tasks(status=TaskStatus.COMPLETED)

    def clear_completed(self) -> int:
        """Remove all completed task files. Returns count of removed tasks."""
        completed_dir = self._dir_for(TaskStatus.COMPLETED)
        count = 0
        for file in completed_dir.glob("task_*.json"):
            file.unlink()
            count += 1
        return count

    def clear_failed(self) -> int:
        """Remove all failed task files. Returns count of removed tasks."""
        failed_dir = self._dir_for(TaskStatus.FAILED)
        count = 0
        for file in failed_dir.glob("task_*.json"):
            file.unlink()
            count += 1
        return count

    def stats(self) -> dict[str, int]:
        """Return a count of tasks per status."""
        return {
            status.value: len(list(self._dir_for(status).glob("task_*.json")))
            for status in TaskStatus
        }

    def __repr__(self) -> str:
        s = self.stats()
        return (
            f"TaskQueue(root={self.root}, "
            f"pending={s['PENDING']}, running={s['RUNNING']}, "
            f"completed={s['COMPLETED']}, failed={s['FAILED']})"
        )
