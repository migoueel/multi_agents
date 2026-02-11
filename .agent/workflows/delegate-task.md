---
description: How to delegate a task to a sub-agent via Agent Maestro
---

# Delegate Task to Sub-Agent

Use this workflow when you need to delegate an atomic/boilerplate task to a specialized sub-agent.

## Prerequisites

- The watcher must be running: `maestro start`
- VS Code must be open with Copilot (GPT-5 mini) available

## Steps

### 1. Create a task JSON file

Write a JSON file to `.agent_bridge/pending/task_<id>.json` with this structure:

```json
{
  "id": "<8-char-hex-id>",
  "agent": "gpt-5-mini",
  "agent_type": "<tester|reviewer or empty for default agent>",
  "action": "<implement|test|refactor|fix|document|review>",
  "target_files": ["path/to/file.py"],
  "instructions": "Clear, specific, self-contained instructions. The sub-agent has ZERO context about your conversation — include everything they need.",
  "context": "Tech stack, coding patterns, related files, constraints, what 'done' looks like.",
  "status": "PENDING",
  "result": null,
  "error": null,
  "created_at": "<ISO-8601 timestamp>",
  "completed_at": null,
  "priority": 0
}
```

**Agent types**: `""` (empty = default VS Code agent, for code changes), `"tester"` (read+write+run), `"reviewer"` (read-only)
**Action types**: `implement`, `test`, `refactor`, `fix`, `document`, `review`, `custom`

### 2. Wait for the watcher to pick it up

The watcher polls every 3 seconds (configurable in `config.yaml`). It will:
1. Move the task to `.agent_bridge/running/`
2. Invoke `copilot -p <prompt>` (adding `--agent <agent_type>` only if agent_type is set)
3. Move to `.agent_bridge/completed/` (or `.agent_bridge/failed/`)

### 3. Check the result

Read the completed task file from `.agent_bridge/completed/task_<id>.json`.
The `result` field contains the sub-agent's summary of what it did.

If the task failed, check `.agent_bridge/failed/task_<id>.json` — the `error` field explains what went wrong.

You can also use the CLI:
```bash
maestro status <task-id>
maestro list --status COMPLETED
```

## Writing Good Task Instructions

Sub-agents have **zero context**. Every task must be self-contained.

**Include:**
- **WHAT**: specific, atomic outcome (one deliverable)
- **WHERE**: exact file paths in `target_files`
- **WHY**: architecture constraints, coding conventions in `context`
- **HOW TO VERIFY**: what "done" looks like

**Bad**: `"Fix the auth bug"`
**Good**: `"In src/auth.py, validate_token() on line 45 doesn't check expiration. Add a check using datetime.utcnow() and raise TokenExpiredError (defined in src/exceptions.py). Follow the pattern in validate_signature()."`

## Tips

- **Keep instructions self-contained**: Assume the sub-agent knows nothing
- **Provide full context**: Include tech stack, file paths, coding conventions
- **Use target_files**: Helps the sub-agent focus on the right files
- **Set priority > 0**: For urgent tasks that should be picked up first
- **Handle failures**: Read the `error` field and retry with clearer instructions
