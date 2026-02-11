"""
Agent Maestro CLI — Unified command-line interface.

Commands:
    maestro init               Scaffold config + dirs + custom agents
    maestro start              Start the watcher daemon
    maestro delegate "..."     Delegate a task to a sub-agent
    maestro status <id>        Check task status
    maestro list               List all tasks
    maestro stats              Show task statistics
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


def _get_scaffold_dir() -> Path:
    """Return the path to the scaffold templates directory."""
    return Path(__file__).parent / "scaffold"


def cmd_init(args: argparse.Namespace) -> None:
    """Scaffold a new project with Agent Maestro config and custom agents.

    File operations are wrapped to provide friendly messages on permission errors.
    """
    project_root = Path(args.project_root).resolve()
    scaffold_dir = _get_scaffold_dir()

    print(f"🎼 Initializing Agent Maestro in {project_root}")

    try:
        # 1. Create .agent_bridge directories
        bridge_dir = project_root / ".agent_bridge"
        for subdir in ("pending", "running", "completed", "failed"):
            (bridge_dir / subdir).mkdir(parents=True, exist_ok=True)
        print(f"  ✅ Created {bridge_dir.relative_to(project_root)}/")

        # 2. Copy config.yaml (if it doesn't exist)
        config_dest = project_root / "config.yaml"
        config_src = scaffold_dir / "config.yaml"
        if not config_dest.exists() and config_src.exists():
            shutil.copy2(config_src, config_dest)
            print(f"  ✅ Created config.yaml")
        elif config_dest.exists():
            print(f"  ⏭️  config.yaml already exists — skipped")

        # 3. Copy custom agent definitions
        agents_dest = project_root / ".github" / "agents"
        agents_src = scaffold_dir / "agents"
        agents_dest.mkdir(parents=True, exist_ok=True)

        if agents_src.exists():
            for agent_file in agents_src.glob("*.agent.md"):
                dest_file = agents_dest / agent_file.name
                if not dest_file.exists():
                    shutil.copy2(agent_file, dest_file)
                    print(f"  ✅ Created .github/agents/{agent_file.name}")
                else:
                    print(f"  ⏭️  .github/agents/{agent_file.name} already exists — skipped")

        print()
        print("🎵 Agent Maestro is ready!")
        print("   Next steps:")
        print("   1. Edit config.yaml with your Copilot CLI path")
        print("   2. Customize .github/agents/ for your workflow")
        print("   3. Run: maestro start")
    except PermissionError as e:
        print(f"❌ Permission error while initializing {project_root}: {e}", file=sys.stderr)
        print("   Try running with elevated permissions or choose a writable directory.", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"❌ Error while initializing {project_root}: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_start(args: argparse.Namespace) -> None:
    """Start the watcher daemon."""
    from .watcher import main as watcher_main
    try:
        watcher_main()
    except PermissionError as e:
        print(f"❌ Permission error starting watcher: {e}", file=sys.stderr)
        print("   Ensure the process can create files/sockets in the project directory.", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"❌ Error starting watcher: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_delegate(args: argparse.Namespace) -> None:
    """Delegate a task to a sub-agent."""
    from . import delegate_task

    task = delegate_task(
        instructions=args.instructions,
        target_files=args.files or [],
        action=args.action,
        agent_type=args.agent_type,
        context=args.context,
        priority=args.priority,
        project_root=args.project_root,
    )

    print(f"📋 Task delegated: {task}")
    print(f"   ID:         {task.id}")
    print(f"   Action:     {task.action}")
    if task.agent_type:
        print(f"   Agent:      @{task.agent_type}")
    print(f"   Files:      {', '.join(task.target_files) or '(none)'}")
    print()
    print(f"   Track with: maestro status {task.id}")


def cmd_retry(args: argparse.Namespace) -> None:
    """Retry a failed task with updated instructions."""
    from . import retry_task

    try:
        task = retry_task(
            args.task_id,
            instructions=args.instructions,
            project_root=args.project_root,
        )
    except FileNotFoundError:
        print(f"❓ Task {args.task_id} not found")
        sys.exit(1)
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)

    print(f"🔁 Task retried: {task}")
    print(f"  New ID:      {task.id}")
    if task.agent_type:
        print(f"  Agent:       @{task.agent_type}")
    print(f"  Files:       {', '.join(task.target_files) or '(none)'}")
    print()
    print(f"  Track with: maestro status {task.id}")


def cmd_status(args: argparse.Namespace) -> None:
    """Check the status of a task."""
    from . import check_status

    task = check_status(args.task_id, project_root=args.project_root)
    if task is None:
        print(f"❓ Task {args.task_id} not found")
        sys.exit(1)

    print(f"Task: {task}")
    print(f"  Status:      {task.status.value}")
    if task.agent_type:
        print(f"  Agent type:  @{task.agent_type}")
    print(f"  Created:     {task.created_at}")
    if task.completed_at:
        print(f"  Completed:   {task.completed_at}")
    if task.result:
        print(f"  Result:      {str(task.result)[:200]}")
    if task.error:
        print(f"  Error:       {task.error}")


def cmd_list(args: argparse.Namespace) -> None:
    """List all tasks."""
    from . import list_tasks
    from .protocol import TaskStatus

    status_filter = None
    if args.status:
        try:
            status_filter = TaskStatus(args.status.upper())
        except ValueError:
            print(f"❌ Invalid status: {args.status}")
            print(f"   Valid: {', '.join(s.value for s in TaskStatus)}")
            sys.exit(1)

    tasks = list_tasks(status=status_filter, project_root=args.project_root)

    if not tasks:
        print("📭 No tasks found")
        return

    for task in tasks:
        print(f"  {task}")


def cmd_stats(args: argparse.Namespace) -> None:
    """Show task queue statistics."""
    from .queue import TaskQueue
    from .config import load_config

    project_root = args.project_root or "."
    cfg = load_config(project_root)
    bridge_dir = Path(project_root) / cfg.get("bridge", {}).get(
        "agent_bridge_dir", ".agent_bridge"
    )
    queue = TaskQueue(bridge_dir)
    stats = queue.stats()

    print("📊 Task Queue Statistics")
    print(f"   ⏳ Pending:   {stats['PENDING']}")
    print(f"   🔄 Running:   {stats['RUNNING']}")
    print(f"   ✅ Completed: {stats['COMPLETED']}")
    print(f"   ❌ Failed:    {stats['FAILED']}")
    total = sum(stats.values())
    print(f"   ── Total:     {total}")


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="maestro",
        description="🎼 Agent Maestro — Multi-agent task orchestration",
    )
    parser.add_argument(
        "--project-root", "-p",
        default=".",
        help="Project root directory (default: current dir)",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ── init ──────────────────────────────────────────────────────────
    init_parser = subparsers.add_parser(
        "init", help="Scaffold config + dirs + custom agents"
    )
    init_parser.set_defaults(func=cmd_init)

    # ── start ─────────────────────────────────────────────────────────
    start_parser = subparsers.add_parser(
        "start", help="Start the watcher daemon"
    )
    start_parser.set_defaults(func=cmd_start)

    # ── delegate ──────────────────────────────────────────────────────
    delegate_parser = subparsers.add_parser(
        "delegate", help="Delegate a task to a sub-agent"
    )
    delegate_parser.add_argument(
        "instructions", help="What the sub-agent should do"
    )
    delegate_parser.add_argument(
        "--files", "-f", nargs="*", default=[],
        help="Target files for the agent to focus on"
    )
    delegate_parser.add_argument(
        "--action", "-a", default="implement",
        help="Task type: implement, test, refactor, fix, review (default: implement)"
    )
    delegate_parser.add_argument(
        "--agent-type", "-t", default="",
        help="Custom agent to route to: tester, reviewer (empty = default agent)"
    )
    delegate_parser.add_argument(
        "--context", "-c", default="",
        help="Extra context for the agent"
    )
    delegate_parser.add_argument(
        "--priority", type=int, default=0,
        help="Priority (0=normal, higher=more urgent)"
    )
    delegate_parser.set_defaults(func=cmd_delegate)

    # ── retry ─────────────────────────────────────────────────────────
    retry_parser = subparsers.add_parser(
        "retry", help="Retry a failed task with updated instructions"
    )
    retry_parser.add_argument("task_id", help="ID of the failed task to retry")
    retry_parser.add_argument(
        "--instructions", "-i", required=True,
        help="New instructions for the retried task"
    )
    retry_parser.set_defaults(func=cmd_retry)

    # ── status────────────────────────────────────────────────────────
    status_parser = subparsers.add_parser(
        "status", help="Check task status"
    )
    status_parser.add_argument("task_id", help="Task ID to check")
    status_parser.set_defaults(func=cmd_status)

    # ── list ──────────────────────────────────────────────────────────
    list_parser = subparsers.add_parser(
        "list", help="List all tasks"
    )
    list_parser.add_argument(
        "--status", "-s", default=None,
        help="Filter by status: PENDING, RUNNING, COMPLETED, FAILED"
    )
    list_parser.set_defaults(func=cmd_list)

    # ── stats ─────────────────────────────────────────────────────────
    stats_parser = subparsers.add_parser(
        "stats", help="Show task queue statistics"
    )
    stats_parser.set_defaults(func=cmd_stats)

    # ── Parse and dispatch ────────────────────────────────────────────
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
