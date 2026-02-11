"""
Watcher — Background daemon that polls for pending tasks and dispatches them.

The watcher continuously scans the task queue for PENDING tasks, claims them,
runs them through the appropriate runner, and records the results.

Usage:
    maestro start              # via CLI
    python -m agent_maestro    # direct
"""

from __future__ import annotations

import signal
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, Future
from pathlib import Path
from typing import Optional

from .protocol import Task, TaskStatus, RunResult
from .queue import TaskQueue
from .runners.base import BaseRunner
from .runners.copilot_runner import CopilotRunner


# ── ANSI colors for terminal output ──────────────────────────────────

class _C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    RED     = "\033[91m"
    CYAN    = "\033[96m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"


def _log(icon: str, msg: str, color: str = _C.RESET) -> None:
    ts = time.strftime("%H:%M:%S")
    print(f"{_C.DIM}{ts}{_C.RESET} {icon} {color}{msg}{_C.RESET}")


class BridgeWatcher:
    """
    Background watcher that polls the task queue and dispatches tasks.

    Args:
        queue:          The TaskQueue to monitor.
        project_root:   Absolute path to the project root.
        runner:         A runner instance (default: CopilotRunner).
        poll_interval:  Seconds between polls.
        max_workers:    Max concurrent tasks.
    """

    def __init__(
        self,
        queue: TaskQueue,
        project_root: str | Path,
        runner: Optional[BaseRunner] = None,
        poll_interval: float = 3.0,
        max_workers: int = 1,
    ):
        self.queue = queue
        self.project_root = str(Path(project_root))
        self.runner = runner or CopilotRunner()
        self.poll_interval = poll_interval
        self.max_workers = max_workers
        self._running = False
        self._active_tasks: dict[str, Future] = {}

    def start(self) -> None:
        """Start the watcher loop. Blocks until stopped."""
        self._running = True
        _log("🚀", "Agent Maestro watcher started", _C.GREEN)
        _log("📂", f"Queue root: {self.queue.root}", _C.DIM)
        _log("🔧", f"Runner: {self.runner.__class__.__name__}", _C.DIM)
        _log("⏱️ ", f"Poll interval: {self.poll_interval}s", _C.DIM)
        _log("👷", f"Max workers: {self.max_workers}", _C.DIM)
        _log("", "─" * 50)
        _log("👂", "Watching for tasks…  (Ctrl+C to stop)", _C.CYAN)
        _log("", "─" * 50)

        # Register signal handlers for graceful shutdown
        # (only works in main thread — skip gracefully in test threads)
        try:
            signal.signal(signal.SIGINT, self._handle_shutdown)
            signal.signal(signal.SIGTERM, self._handle_shutdown)
        except ValueError:
            pass  # Not in main thread — signals handled externally

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            while self._running:
                try:
                    self._poll_cycle(executor)
                except Exception as e:
                    _log("💥", f"Poll cycle error: {e}", _C.RED)
                    traceback.print_exc()

                # Clean up finished futures
                self._cleanup_futures()

                time.sleep(self.poll_interval)

        _log("🛑", "Agent Maestro watcher stopped", _C.YELLOW)

    def stop(self) -> None:
        """Signal the watcher to stop."""
        self._running = False

    def _handle_shutdown(self, signum, frame) -> None:
        _log("", "")
        _log("🛑", "Shutdown signal received…", _C.YELLOW)
        self.stop()

    def _poll_cycle(self, executor: ThreadPoolExecutor) -> None:
        """Check for pending tasks and dispatch them."""
        # Don't pick up new tasks if we're at capacity
        active_count = len(self._active_tasks)
        if active_count >= self.max_workers:
            return

        pending = self.queue.get_pending_tasks()
        if not pending:
            return

        # Pick the highest-priority pending task(s) and claim as many as we have capacity for
        while len(self._active_tasks) < self.max_workers:
            pending = self.queue.get_pending_tasks()
            if not pending:
                break

            task = pending[0]
            _log("📋", f"Found pending task: {task}", _C.BLUE)

            try:
                claimed = self.queue.claim_task(task.id)
                _log("🔄", f"Claimed task [{claimed.id}] → RUNNING", _C.YELLOW)
            except ValueError as e:
                _log("⚠️ ", f"Could not claim task [{task.id}]: {e}", _C.RED)
                # Try next pending task / iteration
                continue

            # Dispatch to runner in a thread using the claimed (fresh) Task object
            future = executor.submit(self._execute_task, claimed)
            self._active_tasks[claimed.id] = future

    def _execute_task(self, task: Task) -> None:
        """Run a task through the runner and record the result."""
        agent_tag = f" @{task.agent_type}" if task.agent_type else ""
        _log("🤖", f"Executing [{task.id}]{agent_tag}: {task.instructions[:60]}…", _C.MAGENTA)

        try:
            result: RunResult = self.runner.execute(task, self.project_root)

            if result.success:
                self.queue.complete_task(task.id, result.output)
                _log("✅", f"Task [{task.id}] COMPLETED", _C.GREEN)
                if result.output:
                    for line in result.output.split("\n")[:5]:
                        _log("  ", f"  {line}", _C.DIM)
            else:
                self.queue.fail_task(task.id, result.error)
                _log("❌", f"Task [{task.id}] FAILED: {result.error}", _C.RED)

        except Exception as e:
            error_msg = f"Runner exception: {e}"
            _log("💥", f"Task [{task.id}] CRASHED: {error_msg}", _C.RED)
            try:
                self.queue.fail_task(task.id, error_msg)
            except Exception:
                pass  # Best-effort error recording

    def _cleanup_futures(self) -> None:
        """Remove completed futures from the active set."""
        done = [tid for tid, f in self._active_tasks.items() if f.done()]
        for tid in done:
            del self._active_tasks[tid]


def main():
    """CLI entry point — start the watcher with default config."""
    from .config import load_config

    project_root = str(Path.cwd())
    config = load_config(project_root)

    bridge_cfg = config.get("bridge", {})
    runner_cfg = config.get("runners", {})

    # Set up queue
    queue_dir = Path(project_root) / bridge_cfg.get("agent_bridge_dir", ".agent_bridge")
    queue = TaskQueue(queue_dir)

    # Set up runner
    cli_cfg = runner_cfg.get("copilot_cli", {})
    runner = CopilotRunner(
        copilot_command=cli_cfg.get("command", "copilot"),
        model=cli_cfg.get("model", "gpt-5-mini"),
        allow_all_tools=cli_cfg.get("allow_all_tools", True),
        allow_all_paths=cli_cfg.get("allow_all_paths", True),
        extra_args=cli_cfg.get("extra_args", []),
        timeout_seconds=bridge_cfg.get("task_timeout_seconds", 300),
    )

    # Start watcher
    watcher = BridgeWatcher(
        queue=queue,
        project_root=project_root,
        runner=runner,
        poll_interval=bridge_cfg.get("poll_interval_seconds", 3),
        max_workers=bridge_cfg.get("max_concurrent_tasks", 1),
    )
    watcher.start()


if __name__ == "__main__":
    main()
