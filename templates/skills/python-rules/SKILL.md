---
name: python-rules
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

Select the interpreter from the project's `.python-version`, `requires-python`,
lockfile, and supported CI matrix. `uv` honors version requests and project
constraints; it does not simply choose the newest installed Python.

```bash
cat .python-version
rg 'requires-python' pyproject.toml
uv python find
uv sync --locked
```

If no project pin exists, establish a compatible version from dependency
support and the project's CI before using `uv python pin <version>` or
`uv sync --python <version>`. Do not overwrite an existing pin with a generic
"stable" version or delete `.venv` to hide a mismatch. See [uv's interpreter
selection rules](https://docs.astral.sh/uv/concepts/python-versions/).

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
