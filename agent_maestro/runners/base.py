"""
Base Runner — Abstract interface for sub-agent execution.

All runners must implement the `execute` method, which takes a Task
and returns a RunResult.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..protocol import Task, RunResult


class BaseRunner(ABC):
    """
    Abstract base class for sub-agent runners.

    A runner is responsible for:
    1. Translating a Task into a command the sub-agent understands
    2. Executing that command (subprocess, API call, etc.)
    3. Capturing the output and returning a RunResult
    """

    @abstractmethod
    def execute(self, task: Task, project_root: str | Path) -> RunResult:
        """
        Execute a task using the sub-agent.

        Args:
            task:         The task to execute.
            project_root: Absolute path to the project root.

        Returns:
            RunResult with success/failure and output.
        """
        ...

    def build_prompt(self, task: Task, project_root: str | None = None) -> str:
        """
        Build a natural-language prompt from a Task.
        Subclasses can override for agent-specific formatting.
        """
        parts: list[str] = []

        parts.append(f"ACTION: {task.action}")
        parts.append(f"INSTRUCTIONS: {task.instructions}")

        if task.target_files:
            files = ", ".join(task.target_files)
            parts.append(f"TARGET FILES: {files}")

        if task.context:
            parts.append(f"CONTEXT: {task.context}")

        parts.append(
            "When done, output a brief summary of what you changed. "
            "Do NOT ask for confirmation — just do the work."
        )

        return "\n\n".join(parts)

    def validate_target_files(self, target_files: list[str], project_root: str) -> list[str]:
        """Validate and normalize target file paths to prevent path traversal.

        Rules:
        1. Reject absolute paths.
        2. Reject any path containing '..' segments.
        3. Resolve each path relative to project_root and ensure the resolved
           path is inside project_root.
        4. Return a list of validated relative paths (relative to project_root).
        """
        if not target_files:
            return []

        project_root_path = Path(project_root).resolve()
        validated: list[str] = []

        for p in target_files:
            if not isinstance(p, str) or p == "":
                raise ValueError(f"Invalid target file: {p!r}")

            candidate = Path(p)

            # Reject absolute paths
            if candidate.is_absolute():
                raise ValueError(f"Absolute paths are not allowed: {p}")

            # Reject paths containing '..' segments
            if ".." in candidate.parts:
                raise ValueError(f"Parent directory segments ('..') are not allowed: {p}")

            # Resolve against project root and ensure it's inside project_root
            resolved = (project_root_path / candidate).resolve()
            try:
                rel = resolved.relative_to(project_root_path)
            except Exception:
                raise ValueError(f"Resolved path escapes project root: {p} -> {resolved}")

            # Return relative path string (use OS-native path sep)
            validated.append(str(rel))

        return validated
