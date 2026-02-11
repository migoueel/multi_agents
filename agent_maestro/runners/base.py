"""
Base Runner — Abstract interface for sub-agent execution.

All runners must implement the `execute` method, which takes a Task
and returns a RunResult.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

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
    def execute(self, task: Task, project_root: str) -> RunResult:
        """
        Execute a task using the sub-agent.

        Args:
            task:         The task to execute.
            project_root: Absolute path to the project root.

        Returns:
            RunResult with success/failure and output.
        """
        ...

    def build_prompt(self, task: Task) -> str:
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
