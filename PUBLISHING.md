# Publishing Agent Maestro to PyPI

This guide explains how to publish Agent Maestro to PyPI so users can install it with `pip install agent-maestro`.

## Prerequisites

1. **PyPI account** — Create one at https://pypi.org/account/register/
2. **Test PyPI account** (optional) — For testing: https://test.pypi.org/account/register/
3. **GitHub repository** — Already set up at `migoueel/multi_agents`

## Setup (One-Time)

### Option 1: Trusted Publishing (Recommended — No API Tokens!)

This is the modern, secure way. The GitHub Actions workflow `.github/workflows/publish.yml` is already configured for this.

1. **Go to PyPI** → https://pypi.org/manage/account/publishing/
2. **Add a new pending publisher**:
   - **PyPI Project Name**: `agent-maestro`
   - **Owner**: `migoueel`
   - **Repository name**: `multi_agents`
   - **Workflow name**: `publish.yml`
   - **Environment name**: Leave blank (or use `release` if you configure one)

3. **That's it!** No API tokens needed. When you create a GitHub release, the workflow will automatically publish to PyPI.

### Option 2: API Token (Alternative)

If you prefer using API tokens:

1. **Generate a token** at https://pypi.org/manage/account/token/
   - Scope: "Entire account" (first-time) or "Project: agent-maestro" (after first publish)
2. **Add to GitHub Secrets**:
   - Go to `Settings` → `Secrets and variables` → `Actions`
   - Create secret: `PYPI_API_TOKEN` = `pypi-...`
3. **Update workflow**: Change `.github/workflows/publish.yml`:
   ```yaml
   - name: Publish to PyPI
     env:
       TWINE_USERNAME: __token__
       TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
     run: twine upload dist/*
   ```

## Publishing a New Release

### 1. Prepare the Release

```bash
# 1. Update version in pyproject.toml
# Change: version = "0.1.0" → "0.2.0"

# 2. Update version in agent_maestro/__init__.py
# Change: __version__ = "0.1.0" → "0.2.0"

# 3. (Optional) Update CHANGELOG.md with release notes

# 4. Commit and push
git add .
git commit -m "chore: bump version to 0.2.0"
git push origin main
```

### 2. Create a Git Tag

```bash
git tag v0.2.0
git push origin v0.2.0
```

### 3. Create a GitHub Release

**Via GitHub Web UI:**

1. Go to https://github.com/migoueel/multi_agents/releases/new
2. **Tag**: Select `v0.2.0` (the tag you just pushed)
3. **Title**: `v0.2.0` or `Agent Maestro v0.2.0`
4. **Description**: Add release notes (features, fixes, breaking changes)
5. Click **Publish release**

**Via GitHub CLI:**

```bash
gh release create v0.2.0 \
  --title "Agent Maestro v0.2.0" \
  --notes "
  ## What's New
  - Added task priority support
  - Fixed watcher crash on malformed JSON
  - Improved error messages
  "
```

### 4. Automatic Publishing

Once you publish the GitHub release:

1. The `publish.yml` workflow automatically triggers
2. It builds the package (`python -m build`)
3. It publishes to PyPI (via trusted publishing or API token)
4. Check the Actions tab to see the workflow run

### 5. Verify

```bash
# Wait a few minutes, then:
pip install --upgrade agent-maestro

# Or check PyPI directly:
# https://pypi.org/project/agent-maestro/
```

## Testing Before Release (Optional)

To test the package before publishing to real PyPI:

### Test on Test PyPI

1. **Configure trusted publishing** on https://test.pypi.org/ (same steps as above)

2. **Manual test publish**:
   ```bash
   # Build
   python -m build

   # Upload to Test PyPI
   twine upload --repository testpypi dist/*

   # Test install
   pip install --index-url https://test.pypi.org/simple/ agent-maestro
   ```

### Local Testing

```bash
# Build locally
python -m build

# Install from local build
pip install dist/agent_maestro-0.2.0-py3-none-any.whl

# Test
maestro --help
```

## Version Numbering

Use [Semantic Versioning](https://semver.org/):

- **MAJOR** (1.0.0): Breaking changes
- **MINOR** (0.2.0): New features, backward compatible
- **PATCH** (0.1.1): Bug fixes, backward compatible

## Troubleshooting

### "Project name already exists"
If `agent-maestro` is taken, choose a different name in `pyproject.toml`:
```toml
name = "agent-maestro-copilot"  # or similar
```

### "Filename has already been used"
You tried to upload the same version twice. Bump the version number.

### Workflow fails with "403 Forbidden"
Check that trusted publishing is configured correctly on PyPI with the exact repository name, owner, and workflow file.

## Maintenance

### Yanking a Release

If you accidentally publish a broken version:

```bash
# Web UI: PyPI → Project → Releases → Yank
# Or via CLI:
twine yank agent-maestro 0.2.0 -m "Broken dependency"
```

### Updating Package Metadata

Edit `pyproject.toml` and publish a new version. Metadata changes only take effect on new releases.

## Resources

- **PyPI Trusted Publishing**: https://docs.pypi.org/trusted-publishers/
- **Python Packaging Guide**: https://packaging.python.org/
- **Semantic Versioning**: https://semver.org/
- **twine docs**: https://twine.readthedocs.io/
