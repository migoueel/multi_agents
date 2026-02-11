"""
Copilot Runner — Executes tasks via GitHub Copilot CLI (gpt-5-mini).

This runner always uses the default VS Code agent (no `--agent` flag) for full
file write capabilities. When `agent_type` is specified on a task, a brief role
instruction is prepended to the prompt to guide behavior:

- `implementer`: "You are implementing code changes..."
- `tester`: "You are writing tests..."
- `reviewer`: "You are reviewing code..." (discourages file changes)

All agents use gpt-5-mini and have identical file editing capabilities.

Docs: https://docs.github.com/en/copilot/concepts/agents/about-copilot-cli
"""

from __future__ import annotations

import re
import subprocess
import tempfile
import shutil
import os
import logging
import stat
import traceback
from pathlib import Path

from ..protocol import Task, RunResult
from .base import BaseRunner

logger = logging.getLogger(__name__)


class CopilotRunner(BaseRunner):
    """
    Executes tasks via GitHub Copilot CLI's programmatic mode.

    Requirements:
    - GitHub Copilot CLI installed (copilot.bat via VS Code extension)
    - Authenticated via `gh auth login`
    - A valid Copilot subscription

    The runner always uses the default VS Code agent (full file write capabilities).
    When `agent_type` is specified, specialized instructions from corresponding
    .agent.md files are injected into the prompt to guide behavior.
    """

    def __init__(
        self,
        copilot_command: str = "copilot",
        model: str = "gpt-5-mini",
        allow_all_tools: bool = False,
        allow_all_paths: bool = False,
        extra_args: list[str] | None = None,
        timeout_seconds: int = 300,
    ):
        self.copilot_command = copilot_command
        self.model = model
        # Default to False for safety; enable explicitly via config
        self.allow_all_tools = allow_all_tools
        self.allow_all_paths = allow_all_paths
        self.extra_args = extra_args or []
        self.timeout_seconds = int(timeout_seconds)

    def execute(self, task: Task, project_root: str | Path) -> RunResult:
        """
        Execute a task by invoking `copilot -p <prompt>`.

        Writes the prompt to a temp file to avoid shell escaping issues
        on Windows (bat → powershell → copilot chain).

        Always uses the default agent for full file write capabilities.
        If agent_type is set, injects specialized instructions from
        .github/agents/<agent_type>.agent.md into the prompt.
        """
        # Normalize project_root to str
        project_root = str(Path(project_root))
        # Validate target files to prevent path traversal
        try:
            validated_files = self.validate_target_files(task.target_files, project_root)
            # Use validated relative paths for subsequent prompt building and execution
            task.target_files = validated_files
        except ValueError as ve:
            logger.error("Invalid target_files: %s", ve)
            return RunResult(success=False, error=str(ve))

        prompt = self.build_prompt(task, project_root)

        # Create a secure temp file for the prompt (avoid mktemp races)
        prompt_tmp = tempfile.NamedTemporaryFile(
            prefix="copilot_prompt_",
            suffix=".txt",
            delete=False,
            mode="w",
            encoding="utf-8",
        )
        prompt_path = Path(prompt_tmp.name)
        output_tmp = None
        try:
            # Write and flush securely
            prompt_tmp.write(prompt)
            prompt_tmp.flush()
            try:
                os.fsync(prompt_tmp.fileno())
            except Exception:
                # os.fsync may not be available on some platforms; ignore
                pass
            prompt_tmp.close()

            # Restrict permissions to owner only where supported
            try:
                os.chmod(prompt_path, stat.S_IRUSR | stat.S_IWUSR)
            except Exception:
                pass

            # Validate copilot_command exists and is executable
            copilot_exe = shutil.which(self.copilot_command)
            if not copilot_exe:
                # If an absolute path was provided, check directly
                if Path(self.copilot_command).is_absolute() and os.access(self.copilot_command, os.X_OK):
                    copilot_exe = self.copilot_command
                else:
                    msg = (
                        f"Command '{self.copilot_command}' not found or not executable. "
                        "Install Copilot CLI: https://docs.github.com/en/copilot/how-tos/set-up/install-copilot-cli"
                    )
                    logger.error(msg)
                    return RunResult(success=False, error=msg)

            # Sanitize extra_args: allow only safe flag/value tokens
            safe_flag_re = re.compile(r"^-{1,2}[A-Za-z0-9][A-Za-z0-9_\-]*$")
            safe_val_re = re.compile(r"^[A-Za-z0-9@._:/\\\-]+$")
            sanitized_extra: list[str] = []
            for a in self.extra_args:
                if safe_flag_re.match(a) or safe_val_re.match(a):
                    sanitized_extra.append(a)
                else:
                    msg = f"Invalid extra arg: {a}"
                    logger.warning(msg)
                    return RunResult(success=False, error=msg)

            # Build argv safely (no shell interpolation)
            cmd: list[str] = [copilot_exe, "--model", self.model]
            if self.allow_all_tools:
                cmd.append("--allow-all-tools")
            if self.allow_all_paths:
                cmd.append("--allow-all-paths")
            cmd.append("--no-ask-user")
            cmd.extend(sanitized_extra)

            # Pass prompt file path to avoid shell escaping issues and very long argv
            cmd.extend(["-p", str(prompt_path)])

            # Execute process streaming output to temp file to avoid OOM
            max_capture = 256 * 1024  # 256KB
            output_tmp = tempfile.NamedTemporaryFile(prefix="copilot_out_", suffix=".log", delete=False, mode="wb")
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=output_tmp,
                    stderr=subprocess.STDOUT,
                    cwd=project_root,
                )
            except FileNotFoundError:
                msg = f"Command '{copilot_exe}' not found when executing."
                logger.error(msg)
                return RunResult(success=False, error=msg)

            try:
                proc.wait(timeout=self.timeout_seconds)
            except subprocess.TimeoutExpired:
                try:
                    proc.kill()
                except Exception:
                    pass
                return RunResult(success=False, error=f"Task timed out after {self.timeout_seconds}s")

            # Ensure output file flushed
            try:
                output_tmp.flush()
                os.fsync(output_tmp.fileno())
            except Exception:
                pass
            output_tmp.close()

            # Read at most last max_capture bytes
            output_bytes = b""
            try:
                with open(output_tmp.name, "rb") as f:
                    f.seek(0, os.SEEK_END)
                    size = f.tell()
                    if size > max_capture:
                        f.seek(-max_capture, os.SEEK_END)
                    else:
                        f.seek(0)
                    output_bytes = f.read()
            except Exception:
                logger.exception("Failed reading process output")

            combined_output = output_bytes.decode("utf-8", errors="replace").strip()

            if proc.returncode == 0:
                out = combined_output or "Task completed (no output captured)."
                return RunResult(success=True, output=out, files_modified=[])
            else:
                err = combined_output or f"Exit code {proc.returncode}"
                return RunResult(success=False, output=combined_output, error=err)

        except Exception as e:
            logger.exception("Unexpected error running copilot")
            msg = f"Runner error: {type(e).__name__}: {str(e)}"
            return RunResult(success=False, error=msg)
        finally:
            # Clean up temp prompt file
            try:
                if prompt_path.exists():
                    prompt_path.unlink()
            except Exception:
                pass
            # Clean up output tmp file
            try:
                if output_tmp is not None and Path(output_tmp.name).exists():
                    Path(output_tmp.name).unlink()
            except Exception:
                pass

    def build_prompt(self, task: Task, project_root: str) -> str:
        """
        Build a prompt for Copilot CLI. Prepends specialized role instructions
        if agent_type is specified, then adds the actual task.
        """
        parts: list[str] = []

        # Prepend specialized role instructions if agent_type is specified
        if task.agent_type:
            role_instructions = self._get_role_instructions(task.agent_type, project_root)
            if role_instructions:
                parts.append(role_instructions)
                parts.append("---")  # Separator between role and task
        
        # The actual task to execute
        parts.append(f"TASK: {task.instructions}")
        
        if task.target_files:
            files = ", ".join(task.target_files)
            parts.append(f"Files: {files}")

        if task.context:
            parts.append(f"Context: {task.context}")

        return " ".join(parts)

    def _get_role_instructions(self, agent_type: str, project_root: str) -> str | None:
        """
        Get concise role instructions for the specified agent type.
        Returns a brief role description, not the full .agent.md content.
        """
        # Simplified role instructions - just the essence of each role
        roles = {
            "implementer": "You are implementing code changes. Follow existing patterns, update tests if they exist, keep changes minimal and focused.",
            "tester": "You are writing tests. Create comprehensive test coverage (happy path, edge cases, errors). Use the project's test framework patterns. Run tests after creating them.",
            "reviewer": "You are reviewing code. Check for bugs, security issues, performance problems, and adherence to patterns. Provide structured feedback. Do not modify files.",
        }
        
        return roles.get(agent_type)
