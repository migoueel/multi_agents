# Agent Maestro Setup Guide

Quick guide to integrate Agent Maestro into your project.

## Installation

```bash
pip install agent-maestro
```

## Initial Setup

### 1. Initialize in Your Project

```bash
cd /path/to/your-project
maestro init
```

This creates:
```
your-project/
├── .agent_bridge/           # Task queue directories
│   ├── pending/
│   ├── running/
│   ├── completed/
│   └── failed/
├── config.yaml              # Agent Maestro configuration
└── .github/agents/          # Custom agent definitions
    ├── orchestrator.agent.md
    ├── implementer.agent.md
    ├── tester.agent.md
    └── reviewer.agent.md
```

### 2. Configure (Optional)

Edit `config.yaml`:

```yaml
bridge:
  poll_interval_seconds: 3        # How often to check for tasks
  max_concurrent_tasks: 1         # Parallel task limit
  task_timeout_seconds: 300       # Task timeout (5 min)
  agent_bridge_dir: ".agent_bridge"

runners:
  default: "copilot-cli"
  copilot_cli:
    command: "copilot"            # Path to copilot CLI
    model: "gpt-5-mini"           # Model to use
    allow_all_tools: true         # Enable file operations
```

### 3. Customize Agents (Optional)

Edit `.github/agents/*.agent.md` to customize agent behavior, add context, or define handoff patterns.

## Starting the Watcher

The watcher monitors `.agent_bridge/pending/` and executes tasks automatically.

```bash
maestro start
```

The watcher runs in the background. To stop it:

```bash
# Find and kill the process (varies by OS)
# Windows:
taskkill /IM python.exe /F

# Linux/Mac:
pkill -f "maestro.*watcher"
```

## Delegating Tasks

### Via CLI

```bash
# Simple task
maestro delegate "Add error handling to the auth module"

# With specific files
maestro delegate "Add unit tests for user validation" \
  --files tests/test_user.py src/user.py \
  --agent-type tester

# With custom agent and priority
maestro delegate "Review the payment processing code for security issues" \
  --files src/payment.py \
  --agent-type reviewer \
  --priority 10
```

### Via Python API

```python
from agent_maestro import delegate_task, check_status

# Delegate a task
task = delegate_task(
    instructions="Refactor the database connection pool",
    target_files=["src/db.py"],
    agent_type="implementer",
    action="refactor",
    context="Use connection pooling best practices. Maintain backward compatibility.",
    priority=5
)

print(f"Created task: {task.task_id}")

# Check status later
status = check_status(task.task_id)
print(f"Status: {status.status}")
if status.status == "COMPLETED":
    print(f"Result: {status.result}")
```

## Monitoring Tasks

```bash
# List all tasks
maestro list

# List by status
maestro list --status PENDING
maestro list --status RUNNING
maestro list --status COMPLETED

# Check specific task
maestro status task_20260211_123045_a1b2c3

# View statistics
maestro stats
```

## Task Lifecycle

```
PENDING → RUNNING → COMPLETED
                  ↘ FAILED
```

Tasks move through states as:
1. **PENDING**: Waiting in queue
2. **RUNNING**: Being executed by a sub-agent
3. **COMPLETED**: Successfully finished
4. **FAILED**: Encountered an error

## Agent Types

| Type | Use For | Example |
|------|---------|---------|
| `implementer` | Code changes, refactors | "Add pagination to the API" |
| `tester` | Writing & running tests | "Add unit tests for auth" |
| `reviewer` | Code review, analysis | "Review security of payment flow" |
| `orchestrator` | Complex multi-step tasks | "Implement user registration feature" |
| *(empty)* | General tasks | Any task |

## Common Workflows

### 1. Feature Implementation

```bash
# Break down a feature into sub-tasks
maestro delegate "Implement user registration endpoint" \
  --files src/api/auth.py --agent-type implementer

maestro delegate "Add tests for user registration" \
  --files tests/test_auth.py --agent-type tester

maestro delegate "Review registration security" \
  --files src/api/auth.py --agent-type reviewer
```

### 2. Bug Fixing

```bash
maestro delegate "Fix authentication token expiry bug" \
  --files src/auth/tokens.py \
  --action fix \
  --context "Users report tokens expire too early. Check TTL calculation."
```

### 3. Refactoring

```bash
maestro delegate "Extract database queries into repository pattern" \
  --files src/models/ src/repositories/ \
  --action refactor \
  --agent-type implementer
```

## Integration with VS Code

Agent Maestro works seamlessly with VS Code Copilot:

1. **Custom Agents**: The `.github/agents/*.agent.md` files define specialized agent roles
2. **Copilot CLI**: The runner uses `copilot --agent <type>` to route tasks
3. **File Operations**: Agents can read, edit, and create files via Copilot tools

## Troubleshooting

### Watcher Not Starting

```bash
# Check if already running
ps aux | grep maestro  # Linux/Mac
tasklist | findstr python  # Windows

# Check logs (if implemented)
tail -f ~/.agent_maestro/watcher.log
```

### Tasks Stuck in PENDING

- Ensure watcher is running: `ps aux | grep maestro`
- Check config: `cat config.yaml`
- Verify Copilot CLI is accessible: `copilot --version`

### Tasks Failing

```bash
# Check failure reason
maestro status <task-id>

# Look at task details
cat .agent_bridge/failed/<task-id>.json
```

## Best Practices

1. **Break down tasks** — Keep each task atomic and focused
2. **Provide context** — Include architecture notes, constraints, related files
3. **Use specific files** — List exact files rather than directories
4. **Monitor progress** — Check `maestro stats` regularly
5. **Review completions** — Verify sub-agent work before merging

## Next Steps

- Read [AGENTS.md](AGENTS.md) for delegation strategy
- Check [CONTRIBUTING.md](CONTRIBUTING.md) to extend functionality
- Browse `.github/agents/` to understand agent roles
- Star the project: https://github.com/migoueel/multi_agents

## Support

- **Issues**: https://github.com/migoueel/multi_agents/issues
- **Discussions**: https://github.com/migoueel/multi_agents/discussions
