# Agent Maestro

> 🎼 Multi-agent task orchestration — delegate work to specialized sub-agents via a file-based queue + Copilot CLI.

## Architecture

```
Orchestrator → maestro delegate → .agent_bridge/pending/ → watcher → Copilot CLI (--agent) → .agent_bridge/completed/
```

## Task Routing

| Task | File(s) |
|---|---|
| Understand the bridge protocol (Task schema) | `agent_maestro/protocol.py` |
| Manage the task queue (create/claim/complete) | `agent_maestro/queue.py` |
| Add a new runner (sub-agent backend) | `agent_maestro/runners/base.py`, `agent_maestro/runners/` |
| Copilot CLI integration + custom agent routing | `agent_maestro/runners/copilot_runner.py` |
| Background watcher daemon | `agent_maestro/watcher.py` |
| Configuration loading | `agent_maestro/config.py` |
| CLI commands (`maestro`) | `agent_maestro/cli.py` |
| Public API (`delegate_task`, `check_status`, etc.) | `agent_maestro/__init__.py` |
| Package definition + entry points | `pyproject.toml` |
| Custom agent definitions | `.github/agents/*.agent.md` |
| Scaffold templates (for `maestro init`) | `agent_maestro/scaffold/` |

## Key Patterns

- **File-based queue**: Tasks are JSON files in `.agent_bridge/{pending,running,completed,failed}/`
- **Status transitions**: `PENDING → RUNNING → COMPLETED` (or `FAILED`)
- **Custom agent routing**: `CopilotRunner` passes `--agent <agent_type>` to route to `.github/agents/<name>.agent.md`
- **Pluggable runners**: Extend `BaseRunner` to add new sub-agent backends
- **The orchestrator writes to `pending/`**, the watcher moves files through the lifecycle

## Quick Start

1. `pip install -e ".[dev]"` — install the package
2. `maestro init` — scaffold config + custom agents
3. `maestro start` — start the watcher daemon
4. `maestro delegate "Add auth module" --agent-type implementer` — delegate a task
5. `maestro status <id>` / `maestro list` / `maestro stats` — track progress
