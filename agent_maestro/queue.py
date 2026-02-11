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

Assumptions and edge cases:
- Claiming a task is implemented as an atomic filesystem rename from
  pending/ -> running/ using os.replace. If the source is missing at
  replace time it is treated as already-claimed by another process.
- _move_task uses os.replace to perform atomic moves and reports an
  explicit FileNotFoundError when the source is gone.
- list_tasks will quarantine malformed JSON files into a quarantine/
  directory instead of silently skipping them.
"""

from __future__ import annotations

import json
import os
import shutil
import logging
from pathlib import Path
from typing import Optional

from .protocol import Task, TaskStatus

logger = logging.getLogger(__name__)


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
        logger.info("Created task %s at %s", task.id, dest)
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """
        Find a task by ID across all status directories.
        Returns None if not found.
        """
        path = self._find_task_path(task_id)
        if path is None:
            return None
        try:
            return Task.from_file(path)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("Failed to parse task %s: %s", path, e)
            return None

    def _find_task_path(self, task_id: str) -> Optional[Path]:
        """Locate the file path for a task by ID."""
        filename = f"task_{task_id}.json"
        for status_dir in _STATUS_DIRS.values():
            path = self.root / status_dir / filename
            if path.exists():
                return path
        return None

    def _replace_status_file(self, task_id: str, from_status: TaskStatus, to_status: TaskStatus) -> Path:
        """
        Atomically move a task file from one status directory to another.
        Raises FileNotFoundError if the source is missing to indicate a
        concurrent move/claim by another process.
        """
        filename = f"task_{task_id}.json"
        src = self._dir_for(from_status) / filename
        dst_dir = self._dir_for(to_status)
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / filename

        try:
            os.replace(str(src), str(dst))
            logger.info("Atomically moved %s -> %s", src, dst)
        except FileNotFoundError:
            logger.error("Failed to move task %s: source not found %s", task_id, src)
            raise FileNotFoundError(f"Task {task_id} was moved by another process")
        except OSError as e:
            logger.error("Failed to move task %s from %s to %s: %s", task_id, src, dst, e)
            raise

        return dst

    def _move_task(self, task: Task, new_status: TaskStatus) -> Path:
        """
        Atomically move a task file from its current directory to the new
        status dir using os.replace. If another process removed the
        source before replace, raise FileNotFoundError to indicate a
        conflicting move.

        Updates the task's status field and re-saves atomically.
        """
        old_path = self._find_task_path(task.id)
        if old_path is None:
            raise FileNotFoundError(f"Task {task.id} not found in queue")

        new_dir = self._dir_for(new_status)
        new_dir.mkdir(parents=True, exist_ok=True)
        new_path = new_dir / task.filename

        if old_path == new_path:
            # Same location — just update contents
            task.save(new_path)
            logger.info("Updated task %s in place at %s", task.id, new_path)
            return new_path

        try:
            # Atomic filesystem move/replace
            os.replace(str(old_path), str(new_path))
            logger.info("Atomically moved %s -> %s", old_path, new_path)
        except FileNotFoundError:
            # Source disappeared — someone else claimed/moved it
            logger.error("Failed to move task %s: source not found %s", task.id, old_path)
            raise FileNotFoundError(f"Task {task.id} was moved by another process")
        except OSError as e:
            logger.error("Failed to move task %s from %s to %s: %s", task.id, old_path, new_path, e)
            raise

        # Now update the task content atomically at the new location
        try:
            task.save(new_path)
            logger.info("Saved updated task %s at %s", task.id, new_path)
        except Exception as e:
            logger.error("Failed to save task %s after move: %s", task.id, e)
            raise

        return new_path

    def claim_task(self, task_id: str) -> Task:
        """
        Atomically move a task from PENDING → RUNNING by renaming the file
        from pending/ to running/. If the source file is missing at rename
        time it is treated as already claimed by another process.
        """
        filename = f"task_{task_id}.json"
        pending_path = self._dir_for(TaskStatus.PENDING) / filename
        running_dir = self._dir_for(TaskStatus.RUNNING)
        running_dir.mkdir(parents=True, exist_ok=True)
        running_path = running_dir / filename

        if not pending_path.exists():
            # Check if task exists in another status directory
            task = self.get_task(task_id)
            if task is not None:
                logger.info("Claim attempted for %s but status is %s, expected PENDING", task_id, task.status)
                raise ValueError(f"Task {task_id} is {task.status.value}, expected PENDING")
            logger.error("Claim attempted for %s but not found", task_id)
            raise ValueError(f"Task {task_id} not found")

        # Delegate atomic move to helper which preserves race semantics
        try:
            new_path = self._replace_status_file(task_id, TaskStatus.PENDING, TaskStatus.RUNNING)
            logger.info("Atomically claimed task %s: %s -> %s", task_id, pending_path, new_path)
        except FileNotFoundError:
            logger.info("Claim race: task %s missing at rename time", task_id)
            raise ValueError(f"Task {task_id} already claimed")
        except OSError as e:
            logger.error("Failed to claim task %s: %s", task_id, e)
            raise

        # Load, mark running and save atomically
        try:
            task = Task.from_file(new_path)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            quarantine_dir = self.root / "quarantine"
            quarantine_dir.mkdir(parents=True, exist_ok=True)
            qpath = quarantine_dir / running_path.name
            try:
                os.replace(str(new_path), str(qpath))
                logger.warning("Quarantined malformed task %s -> %s: %s", new_path, qpath, e)
            except FileNotFoundError:
                logger.warning("Malformed task disappeared before quarantine: %s", new_path)
            except Exception as ex:
                logger.error("Failed to quarantine malformed task %s: %s", new_path, ex)
            raise ValueError(f"Task {task_id} file is malformed") from e
        if task.status != TaskStatus.PENDING:
            logger.error("Claimed task %s had unexpected status %s", task_id, task.status)
            raise ValueError(f"Task {task_id} had unexpected status {task.status}")
        task.mark_running()
        task.save(new_path)
        logger.info("Task %s marked RUNNING", task_id)
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
                except (json.JSONDecodeError, KeyError, TypeError) as e:
                    # Quarantine malformed task files instead of silently skipping
                    quarantine_dir = self.root / "quarantine"
                    quarantine_dir.mkdir(parents=True, exist_ok=True)
                    qpath = quarantine_dir / file.name
                    try:
                        os.replace(str(file), str(qpath))
                        logger.warning("Quarantined malformed task %s -> %s: %s", file, qpath, e)
                    except FileNotFoundError:
                        logger.warning("Malformed task disappeared before quarantine: %s", file)
                    except Exception as ex:
                        logger.error("Failed to quarantine malformed task %s: %s", file, ex)
                    continue

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
