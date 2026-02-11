"""
Agent Maestro Protocol — Task schema and status definitions.

This module defines the canonical data structures used by the entire system:
orchestrator, queue, watcher, and runners all speak this protocol.

Assumptions and edge cases:
- save() writes atomically by writing to a temporary file in the same
  directory and then using os.replace to publish the final file. This
  ensures other processes will either see the old or the new complete
  file, not a partial write.
- fsync is attempted where supported to reduce data loss on crashes.
- from_file still reads the whole file; callers should handle JSON errors
  and may choose to quarantine malformed files.
"""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional


class TaskStatus(str, Enum):
    """Lifecycle states a task can be in."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class TaskAction(str, Enum):
    """Well-known action types the orchestrator can request."""
    IMPLEMENT = "implement"
    TEST = "test"
    REFACTOR = "refactor"
    FIX = "fix"
    DOCUMENT = "document"
    REVIEW = "review"
    CUSTOM = "custom"


@dataclass
class Task:
    """
    A single unit of work delegated from the orchestrator to a sub-agent.

    Attributes:
        id:             Unique task identifier (auto-generated if omitted).
        agent:          Target sub-agent model, e.g. "gpt-5-mini".
        agent_type:     Custom agent to route to (implementer, tester, etc.).
        action:         What kind of work (implement, test, refactor…).
        target_files:   List of file paths the agent should focus on.
        instructions:   Natural-language instructions for the sub-agent.
        status:         Current lifecycle state.
        context:        Extra context from the orchestrator (architecture
                        notes, constraints, related files, etc.).
        result:         Output / summary written by the sub-agent on success.
        error:          Error message if the task failed.
        created_at:     ISO-8601 timestamp of creation.
        completed_at:   ISO-8601 timestamp of completion (or failure).
        priority:       0 = normal, higher = more urgent (picked first).
    """
    instructions: str
    agent: str = "gpt-5-mini"
    agent_type: str = ""
    action: str = TaskAction.IMPLEMENT.value
    target_files: list[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    context: str = ""
    result: Optional[str] = None
    error: Optional[str] = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    completed_at: Optional[str] = None
    priority: int = 0

    # ── Serialization ────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Serialize to a JSON-friendly dict."""
        data = asdict(self)
        data["status"] = self.status.value if isinstance(self.status, TaskStatus) else self.status
        return data

    def to_json(self, indent: int = 2) -> str:
        """Serialize to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict) -> Task:
        """Deserialize from a dict."""
        data = data.copy()
        raw_status = data.get("status", "PENDING")
        data["status"] = TaskStatus(raw_status) if isinstance(raw_status, str) else raw_status
        # Handle legacy tasks without agent_type
        if "agent_type" not in data:
            data["agent_type"] = ""
        return cls(**data)

    @classmethod
    def from_json(cls, text: str) -> Task:
        """Deserialize from a JSON string."""
        return cls.from_dict(json.loads(text))

    @classmethod
    def from_file(cls, path: Path | str) -> Task:
        """Load a task from a JSON file."""
        return cls.from_json(Path(path).read_text(encoding="utf-8"))

    def save(self, path: Path | str) -> None:
        """Save the task to a JSON file atomically.

        Writes to a temporary file in the same directory, fsyncs if possible,
        and then atomically replaces the target file using os.replace.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        text = self.to_json()
        tmp = None
        try:
            # Create unpredictable temporary file in the same directory
            # and write data ensuring it is flushed and fsynced.
            with tempfile.NamedTemporaryFile(delete=False, dir=path.parent, prefix=".task_", suffix=".tmp", mode="w", encoding="utf-8") as tf:
                tmp = Path(tf.name)
                tf.write(text)
                tf.flush()
                try:
                    os.fsync(tf.fileno())
                except (AttributeError, OSError):
                    # fsync may not be available on some platforms/filesystems
                    pass
            # Atomically replace the final file
            os.replace(str(tmp), str(path))
        finally:
            # Clean up leftover tmp if it still exists
            try:
                if tmp is not None and tmp.exists():
                    tmp.unlink()
            except Exception:
                pass

    # ── Lifecycle helpers ────────────────────────────────────────────

    def mark_running(self) -> None:
        self.status = TaskStatus.RUNNING

    def mark_completed(self, result: str) -> None:
        self.status = TaskStatus.COMPLETED
        self.result = result
        self.completed_at = datetime.now(timezone.utc).isoformat()

    def mark_failed(self, error: str) -> None:
        self.status = TaskStatus.FAILED
        self.error = error
        self.completed_at = datetime.now(timezone.utc).isoformat()

    def is_terminal(self) -> bool:
        return self.status in {TaskStatus.COMPLETED, TaskStatus.FAILED}

    @property
    def filename(self) -> str:
        """Canonical filename for this task."""
        return f"task_{self.id}.json"

    def __str__(self) -> str:
        status_icon = {
            TaskStatus.PENDING: "⏳",
            TaskStatus.RUNNING: "🔄",
            TaskStatus.COMPLETED: "✅",
            TaskStatus.FAILED: "❌",
        }
        icon = status_icon.get(self.status, "❓")
        agent_tag = f" @{self.agent_type}" if self.agent_type else ""
        return f"{icon} [{self.id}] {self.action}{agent_tag}: {self.instructions[:60]}…"


@dataclass
class RunResult:
    """Result returned by a runner after executing a task."""
    success: bool
    output: str = ""
    error: str = ""
    files_modified: list[str] = field(default_factory=list)
