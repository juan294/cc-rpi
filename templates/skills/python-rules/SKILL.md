---
name: "Python Development"
description: "Python-specific patterns: uv/poetry virtual environments, python -m imports, version pinning, pip restrictions on macOS."
---

# Python Development

## Virtual Environment Runner

Wrong -- bare python3 has no project dependencies:

```bash
python3 scripts/run_analysis.py
# ModuleNotFoundError: No module named 'pandas'
```

Right -- use the project's venv runner:

```bash
uv run python scripts/run_analysis.py
# Or: poetry run python scripts/run_analysis.py
# Or: pipenv run python scripts/run_analysis.py
```

## Package-Relative Imports

Wrong -- direct execution breaks relative imports:

```bash
python scripts/etl/transform.py
# ModuleNotFoundError: No module named 'scripts.etl.utils'
```

Right -- use -m for scripts with package imports:

```bash
python -m scripts.etl.transform
```

## Python Version for uv

Wrong -- uv auto-selects newest Python, packages lack wheels:

```bash
uv sync
# error: No wheel found for numpy on Python 3.14
```

Right -- specify a stable Python version:

```bash
# Check project requirements:
cat .python-version
# Pin the version:
uv sync --python 3.13
```

## pip on macOS

Wrong -- system pip blocked by PEP 668 on macOS:

```bash
pip3 install httpie
# error: externally-managed-environment
```

Right -- use brew for CLI tools, pipx for Python apps:

```bash
brew install httpie
# Or for Python-specific apps:
pipx install httpie
```
