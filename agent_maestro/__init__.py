# Agent Maestro — Multi-Agent Task Orchestration
# Delegates atomic tasks from an orchestrator to sub-agents via a file-based queue.

__version__ = "0.1.0"

from .protocol import Task, TaskStatus, TaskAction, RunResult
from .queue import TaskQueue
from .watcher import BridgeWatcher
from pathlib import Path

__all__ = [
    "Task",
    "TaskStatus",
    "TaskAction",
    "RunResult",
    "TaskQueue",
    "BridgeWatcher",
]


def delegate_task(
    instructions: str,
    target_files: list[str] | None = None,
    action: str = "implement",
    agent: str = "gpt-5-mini",
    agent_type: str = "",
    context: str = "",
    priority: int = 0,
    project_root: str | Path | None = None,
) -> Task:
    """
    Create a new task and add it to the pending queue.

    This is the primary function the orchestrator calls to delegate work.

    Args:
        instructions:  What the sub-agent should do (natural language).
        target_files:  Files the sub-agent should focus on.
        action:        Type of work (implement, test, refactor, fix, etc.).
        agent:         Which model to use (default: gpt-5-mini).
        agent_type:    Custom agent to route to (implementer, tester, reviewer).
        context:       Extra context (architecture notes, constraints…).
        priority:      0 = normal, higher = more urgent.
        project_root:  Project root path (auto-detected if omitted).

    Returns:
        The created Task object with its auto-generated ID.
    """
    from pathlib import Path
    from .config import load_config

    if project_root is None:
        project_root = str(Path.cwd())
    else:
        project_root = str(Path(project_root))

    cfg = load_config(project_root)
    bridge_dir = Path(project_root) / cfg.get("bridge", {}).get(
        "agent_bridge_dir", ".agent_bridge"
    )
    queue = TaskQueue(bridge_dir)
    task = queue.create_task(
        instructions=instructions,
        agent=agent,
        action=action,
        target_files=target_files or [],
        context=context,
        priority=priority,
        agent_type=agent_type,
    )
    return task


def retry_task(
    task_id: str,
    instructions: str,
    project_root: str | Path | None = None,
) -> Task:
    """
    Retry a failed task by creating a new PENDING task with updated instructions.
    """
    from pathlib import Path
    from .config import load_config

    if project_root is None:
        project_root = str(Path.cwd())
    else:
        project_root = str(Path(project_root))

    cfg = load_config(project_root)
    bridge_dir = Path(project_root) / cfg.get("bridge", {}).get(
        "agent_bridge_dir", ".agent_bridge"
    )
    queue = TaskQueue(bridge_dir)

    orig = queue.get_task(task_id)
    if orig is None:
        raise FileNotFoundError(f"Task {task_id} not found")
    if orig.status != TaskStatus.FAILED:
        raise ValueError(
            f"Task {task_id} is {orig.status.value}, expected FAILED"
        )

    new_task = queue.create_task(
        instructions=instructions,
        agent=orig.agent,
        action=orig.action,
        target_files=orig.target_files,
        context=orig.context,
        priority=orig.priority,
        agent_type=orig.agent_type,
    )
    return new_task


def check_status(task_id: str, project_root: str | Path | None = None) -> Task | None:
    """Check the current status of a delegated task."""
    from pathlib import Path
    from .config import load_config

    if project_root is None:
        project_root = str(Path.cwd())
    else:
        project_root = str(Path(project_root))

    cfg = load_config(project_root)
    bridge_dir = Path(project_root) / cfg.get("bridge", {}).get(
        "agent_bridge_dir", ".agent_bridge"
    )
    queue = TaskQueue(bridge_dir)
    return queue.get_task(task_id)


def list_tasks(
    status: TaskStatus | None = None,
    project_root: str | Path | None = None,
) -> list[Task]:
    """List all tasks, optionally filtered by status."""
    from pathlib import Path
    from .config import load_config

    if project_root is None:
        project_root = str(Path.cwd())
    else:
        project_root = str(Path(project_root))

    cfg = load_config(project_root)
    bridge_dir = Path(project_root) / cfg.get("bridge", {}).get(
        "agent_bridge_dir", ".agent_bridge"
    )
    queue = TaskQueue(bridge_dir)
    return queue.list_tasks(status=status)
