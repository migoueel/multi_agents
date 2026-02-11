---
description: How to delegate a task to a sub-agent via the bridge system
---

# Delegate Task to Sub-Agent

Use this workflow when the orchestrator (Antigravity) needs to delegate an atomic/boilerplate task to a VS Code sub-agent (GPT-5 mini).

## Prerequisites

- The bridge watcher must be running: `python start_bridge.py`
- VS Code must be open with Copilot (GPT-5 mini) available

## Steps

### 1. Create the task JSON file

Write a JSON file to `.agent_bridge/pending/task_<id>.json` with this structure:

```json
{
  "id": "<8-char-hex-id>",
  "agent": "gpt-5-mini",
  "action": "implement",
  "target_files": ["path/to/file.py"],
  "instructions": "Clear, specific instructions for the sub-agent",
  "status": "PENDING",
  "context": "Any extra context from the orchestrator",
  "result": null,
  "error": null,
  "created_at": "<ISO-8601 timestamp>",
  "completed_at": null,
  "priority": 0
}
```

**Action types**: `implement`, `test`, `refactor`, `fix`, `document`, `review`, `custom`

### 2. Wait for the watcher to pick it up

The watcher polls every 3 seconds (configurable in `config.yaml`). It will:
1. Move the task to `.agent_bridge/running/`
2. Invoke `code chat --mode agent` with the task instructions
3. Move to `.agent_bridge/completed/` (or `.agent_bridge/failed/`)

### 3. Check the result

Read the completed task file from `.agent_bridge/completed/task_<id>.json`.
The `result` field contains the sub-agent's summary of what it did.

## Alternative: Use the CLI

```bash
python orchestrator.py delegate "Write unit tests for utils.py" --files src/utils.py --action test
python orchestrator.py status <task_id>
python orchestrator.py list --status COMPLETED
```

## Tips

- **Keep instructions specific**: "Implement a JWT validation function using the jose library" is better than "Do auth stuff"
- **Provide context**: Include architecture constraints, coding style notes, etc.
- **Use target_files**: Helps the sub-agent focus on the right files
- **Set priority > 0**: For urgent tasks that should be picked up first
