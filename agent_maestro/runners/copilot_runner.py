"""
Copilot Runner — Triggers GitHub Copilot CLI with custom agent routing.

This runner invokes `copilot -p <prompt>` to dispatch a task to a
specific model (default: GPT-5 mini) using the Copilot CLI's
programmatic mode. When `agent_type` is set on the task, the runner
passes `--agent <name>` to route to the corresponding custom agent
defined in `.github/agents/`.

Docs: https://docs.github.com/en/copilot/concepts/agents/about-copilot-cli
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from ..protocol import Task, RunResult
from .base import BaseRunner


class CopilotRunner(BaseRunner):
    """
    Executes tasks via GitHub Copilot CLI's programmatic mode.

    Requirements:
    - GitHub Copilot CLI installed (copilot.bat via VS Code extension)
    - Authenticated via `gh auth login`
    - A valid Copilot subscription

    The runner uses `copilot -p <prompt> --model <model> --allow-all-tools`
    to execute tasks non-interactively. When a task has an `agent_type`,
    it adds `--agent <name>` to route to the matching `.agent.md` file.
    """

    def __init__(
        self,
        copilot_command: str = "copilot",
        model: str = "gpt-5-mini",
        allow_all_tools: bool = True,
        extra_args: list[str] | None = None,
        timeout_seconds: int = 300,
    ):
        self.copilot_command = copilot_command
        self.model = model
        self.allow_all_tools = allow_all_tools
        self.extra_args = extra_args or []
        self.timeout_seconds = timeout_seconds

    def execute(self, task: Task, project_root: str) -> RunResult:
        """
        Execute a task by invoking `copilot -p <prompt>`.

        Writes the prompt to a temp file to avoid shell escaping issues
        on Windows (bat → powershell → copilot chain).

        If the task has an `agent_type`, passes `--agent <agent_type>`
        to route to the corresponding custom agent.
        """
        prompt = self.build_prompt(task)

        # Write prompt to a temp file to avoid shell escaping issues
        # The bat→powershell chain on Windows mangles multi-line strings
        prompt_file = Path(tempfile.mktemp(suffix=".txt", prefix="copilot_prompt_"))
        try:
            prompt_file.write_text(prompt, encoding="utf-8")

            # Build a PowerShell command that reads the prompt from the file
            # into a variable, then calls copilot with it. This avoids all
            # shell escaping issues with the bat→powershell chain.
            copilot_args = f'--model {self.model}'
            if self.allow_all_tools:
                copilot_args += " --allow-all-tools"

            # Route to custom agent if agent_type is specified
            if task.agent_type:
                copilot_args += f" --agent {task.agent_type}"

            for arg in self.extra_args:
                copilot_args += f" {arg}"

            ps_script = (
                f'$p = Get-Content -Raw "{prompt_file}"; '
                f'& "{self.copilot_command}" -p $p {copilot_args}'
            )

            ps_cmd = [
                "powershell", "-NoProfile", "-Command", ps_script
            ]

            result = subprocess.run(
                ps_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout_seconds,
                cwd=project_root,
            )

            combined_output = result.stdout.strip() if result.stdout else ""

            if result.returncode == 0:
                output = combined_output or "Task completed (no output captured)."
                return RunResult(
                    success=True,
                    output=output,
                    files_modified=[],
                )
            else:
                return RunResult(
                    success=False,
                    output=combined_output,
                    error=combined_output or f"Exit code {result.returncode}",
                )

        except subprocess.TimeoutExpired:
            return RunResult(
                success=False,
                error=f"Task timed out after {self.timeout_seconds}s",
            )
        except FileNotFoundError:
            return RunResult(
                success=False,
                error=(
                    f"Command '{self.copilot_command}' not found. "
                    "Install Copilot CLI: https://docs.github.com/en/copilot/how-tos/set-up/install-copilot-cli"
                ),
            )
        except Exception as e:
            return RunResult(
                success=False,
                error=f"Unexpected error: {e}",
            )
        finally:
            # Clean up temp prompt file
            try:
                prompt_file.unlink(missing_ok=True)
            except Exception:
                pass

    def build_prompt(self, task: Task) -> str:
        """
        Build a prompt optimized for Copilot CLI programmatic mode.
        Uses a single-line format to avoid shell escaping issues.
        """
        parts: list[str] = []

        parts.append(
            "You are a sub-agent receiving a delegated task from an orchestrator. "
            "Execute the task autonomously. Do NOT ask for clarification — "
            "use your best judgment. When done, output a concise summary of "
            "what you did."
        )

        parts.append(f"Task type: {task.action.upper()}")
        parts.append(f"Instructions: {task.instructions}")

        if task.target_files:
            files = ", ".join(task.target_files)
            parts.append(f"Target files: {files}")

        if task.context:
            parts.append(f"Context: {task.context}")

        return " | ".join(parts)
