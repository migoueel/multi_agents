# Contributing to Agent Maestro

Thank you for your interest in contributing to Agent Maestro! This document provides guidelines and instructions for contributing.

## Development Setup

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/multi_agents.git
   cd multi_agents
   ```

2. **Install in development mode**
   ```bash
   pip install -e ".[dev]"
   ```

3. **Run tests**
   ```bash
   pytest tests/ -v
   ```

## Project Structure

```
agent_maestro/
├── __init__.py           # Public API exports
├── cli.py                # CLI commands
├── protocol.py           # Task & status schemas
├── queue.py              # File-based task queue
├── watcher.py            # Background daemon
├── config.py             # Configuration loader
├── runners/              # Sub-agent execution backends
│   ├── base.py           # Abstract runner interface
│   └── copilot_runner.py # VS Code Copilot CLI integration
└── scaffold/             # Templates for `maestro init`
    ├── config.yaml
    └── agents/           # Custom agent definitions
```

## Making Changes

### Before You Start

1. **Check existing issues** — see if someone is already working on it
2. **Open an issue** — discuss your idea before major changes
3. **Create a branch** — use descriptive names: `feature/task-priority`, `fix/watcher-crash`

### Code Guidelines

- **Python 3.10+** — use modern Python features (type hints, match statements, etc.)
- **Type hints** — add type annotations for function signatures
- **Docstrings** — document public functions and classes
- **Keep it simple** — prefer clarity over cleverness

### Testing

- **Write tests** for new features
- **Run the full test suite** before submitting: `pytest tests/ -v`
- **Test on multiple platforms** if possible (Windows, Linux, macOS)

Key test files:
- `test_queue.py` — task lifecycle and queue operations
- `test_protocol.py` — task serialization
- `test_e2e.py` — end-to-end watcher + runner integration
- `test_concurrent_claim.py` — race condition handling

## Pull Request Process

1. **Update tests** — ensure all tests pass
2. **Update docs** — if you changed the API or CLI, update README.md
3. **Commit messages** — use clear, descriptive messages
   - ✅ `fix: prevent watcher crash on malformed JSON`
   - ✅ `feat: add task priority support`
   - ❌ `updated stuff`

4. **Submit PR** — describe what changed and why
5. **Wait for review** — maintainers will review and may request changes

## Adding New Features

### Example: Adding a New Runner

If you want to add a new sub-agent backend (e.g., for Anthropic Claude, Ollama, etc.):

1. Create `agent_maestro/runners/your_runner.py`
2. Extend `BaseRunner` from [`runners/base.py`](agent_maestro/runners/base.py)
3. Implement `run_task(task: Task) -> RunResult`
4. Register in config: `config.yaml` → `runners.your_runner`
5. Add tests in `tests/test_your_runner.py`

### Example: Adding a New CLI Command

1. Add command function in [`cli.py`](agent_maestro/cli.py)
2. Use `click` decorators for arguments/options
3. Update README CLI Reference section
4. Test manually: `maestro your-command --help`

## Release Process (Maintainers)

1. **Bump version** in `pyproject.toml` and `agent_maestro/__init__.py`
2. **Update CHANGELOG** (if present) or add release notes
3. **Tag release**: `git tag v0.2.0 && git push origin v0.2.0`
4. **Create GitHub Release** — the `publish.yml` workflow auto-publishes to PyPI

## Questions?

- **Open an issue** — for bugs or feature requests
- **Discussions** — for general questions or ideas

## Code of Conduct

Be respectful, constructive, and welcoming. This is a collaborative project and everyone should feel comfortable contributing.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
