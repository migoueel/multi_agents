# Agent Maestro

> 🎼 Multi-agent task orchestration — delegate work from an orchestrator to specialized sub-agents via a file-based queue.

## Architecture

```
Orchestrator (Antigravity) → maestro delegate → .agent_bridge/pending/ → watcher → Copilot CLI → .agent_bridge/completed/
                                                                                      ↓
                                                                            --agent <name>
                                                                                      ↓
                                                                        .github/agents/*.agent.md
```

## Custom Agents

Agent Maestro leverages VS Code Copilot's [custom agents](https://code.visualstudio.com/docs/copilot/agents/overview) for specialized roles:

| Agent | Role | Handoffs |
|-------|------|----------|
| **Orchestrator** | Plan tasks, coordinate sub-agents | → Implementer, Tester, Reviewer |
| **Implementer** | Write code changes | (worker) |
| **Tester** | Write and run tests | (worker) |
| **Reviewer** | Read-only code review | (worker) |

Agent definitions live in `.github/agents/` and are routed via `--agent <name>` when the watcher invokes Copilot CLI.

## Quick Start

```bash
# 1. Install the package
pip install -e ".[dev]"

# 2. Scaffold config + custom agents
maestro init

# 3. Start the watcher daemon
maestro start

# 4. Delegate a task
maestro delegate "Add error handling to auth module" \
  --files src/auth.py \
  --agent-type implementer

# 5. Check status
maestro status <task-id>
maestro list
maestro stats
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `maestro init` | Scaffold `.agent_bridge/`, `config.yaml`, `.github/agents/` |
| `maestro start` | Start the background watcher daemon |
| `maestro delegate "<instructions>"` | Delegate a task to a sub-agent |
| `maestro status <id>` | Check task status |
| `maestro list [--status PENDING]` | List all tasks |
| `maestro stats` | Show queue statistics |

### Delegate Options

```
maestro delegate "..." [OPTIONS]

  --files, -f      Target files for the agent
  --action, -a     Task type: implement, test, refactor, fix, review
  --agent-type, -t Custom agent: orchestrator, implementer, tester, reviewer
  --context, -c    Extra context string
  --priority       Priority level (0=normal, higher=urgent)
```

## Configuration

Edit `config.yaml` in your project root:

```yaml
bridge:
  poll_interval_seconds: 3
  max_concurrent_tasks: 1
  task_timeout_seconds: 300
  agent_bridge_dir: ".agent_bridge"

runners:
  default: "copilot-cli"
  copilot_cli:
    command: "copilot"       # path to copilot.bat
    model: "gpt-5-mini"
    allow_all_tools: true
```

## Package Structure

```
agent_maestro/
├── __init__.py           # Public API: delegate_task, check_status, list_tasks
├── __main__.py           # python -m agent_maestro
├── cli.py                # maestro CLI commands
├── protocol.py           # Task, TaskStatus, RunResult schemas
├── queue.py              # File-based task queue
├── config.py             # YAML config loader
├── watcher.py            # Background watcher daemon
├── runners/
│   ├── base.py           # Abstract BaseRunner
│   └── copilot_runner.py # Copilot CLI runner with --agent support
└── scaffold/
    ├── config.yaml       # Default config template
    └── agents/           # Custom agent templates
        ├── orchestrator.agent.md
        ├── implementer.agent.md
        ├── tester.agent.md
        └── reviewer.agent.md
```

## How It Works

1. **Task Creation**: `maestro delegate` (or `delegate_task()` from Python) writes a JSON file to `.agent_bridge/pending/`
2. **Watcher Pickup**: The background watcher polls for pending tasks, claims the highest-priority one
3. **Runner Dispatch**: The `CopilotRunner` invokes `copilot -p <prompt> --agent <agent_type>` 
4. **Custom Agent**: Copilot CLI loads the matching `.github/agents/<name>.agent.md` for specialized behavior
5. **Result Recording**: Output moves to `.agent_bridge/completed/` (or `failed/`)

## Testing

```bash
pytest tests/ -v
```

## License

MIT
