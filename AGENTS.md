# Agent Maestro

> 🎼 Multi-agent task orchestration — delegate work to specialized sub-agents via a file-based queue + Copilot CLI.

## Architecture

```
Orchestrator → writes JSON to .agent_bridge/pending/ → watcher → Copilot CLI (--agent) → .agent_bridge/completed/
```

## Delegation Strategy

### When to Delegate

Ask these 4 questions. If **2+ are YES** → delegate.

| # | Question |
|---|----------|
| 1 | Does the task touch **multiple unrelated files**? |
| 2 | Is the task **boilerplate / mechanical**? |
| 3 | Can sub-tasks run **in parallel**? |
| 4 | Is the task **outside your specialty**? |

**Do NOT delegate**: simple questions, single-file edits, planning/architecture decisions.

### How to Delegate

**Create a task JSON file** in `.agent_bridge/pending/task_<id>.json`. The watcher picks it up and dispatches it automatically.

Sub-agents have **zero context** — every task must be **self-contained** with:
- `instructions` — specific, atomic outcome
- `target_files` — exact file paths
- `context` — tech stack, patterns, related files, constraints, what "done" looks like

See `.github/agents/orchestrator.agent.md` for the full JSON schema and examples.

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
- **Custom agent routing**: When `agent_type` is set, `CopilotRunner` passes `--agent <name>` to route to `.github/agents/<name>.agent.md`. Empty `agent_type` uses the default VS Code agent.
- **Pluggable runners**: Extend `BaseRunner` to add new sub-agent backends
- **The orchestrator writes to `pending/`**, the watcher moves files through the lifecycle

## Agent Capabilities & File Writing

The runner **always uses the default VS Code agent** (gpt-5-mini) for full file write capabilities.

When `agent_type` is specified, a brief role instruction is **prepended to the prompt** to guide behavior. All agent types have identical file editing capabilities.

| `agent_type` | Role Instruction | Best For | File Writing |
|---|---|---|---|
| `""` (empty) | Generic sub-agent | Simple tasks | ✅ Can write files |
| `"implementer"` | Code implementation focus | Code changes, refactors | ✅ Can write files |
| `"tester"` | Test writing focus | Writing & running tests | ✅ Can write files |
| `"reviewer"` | Code review focus | Analysis & feedback | ✅ Can write files (but role discourages it) |

**All agent types have full capabilities.** The `agent_type` only changes the initial role instruction, not permissions.

## Quick Start

1. `pip install -e ".[dev]"` — install the package
2. `maestro init` — scaffold config + custom agents
3. `maestro start` — start the watcher daemon
4. Create a task JSON file in `.agent_bridge/pending/` to delegate work
5. `maestro status <id>` / `maestro list` / `maestro stats` — track progress
