"""Execute documented recipes in disposable directories and local processes."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def fence(path, marker, language):
    content = (ROOT / path).read_text().split(marker, 1)[1]
    return re.search(r'```' + language + r'\n(.*?)```', content, re.S)[1]


class RecipeTests(unittest.TestCase):
    def test_sequential_gate_keeps_earlier_failure(self):
        recipe = fence('templates/skills/shell-tools/SKILL.md', 'collect each status', 'bash')
        with tempfile.TemporaryDirectory() as tmp:
            stub = Path(tmp) / 'pnpm'
            stub.write_text('#!/bin/sh\n[ "$2" != typecheck ] || exit 7\nexit 0\n')
            stub.chmod(0o700)
            result = subprocess.run(['bash', '-c', recipe], env={**os.environ, 'PATH': tmp + os.pathsep + os.environ['PATH']}, check=False)
        self.assertEqual(result.returncode, 7)

    def test_node_executes_hashbang_with_both_module_formats(self):
        self.assertIsNotNone(shutil.which('node'), 'Node is required for recipe validation')
        with tempfile.TemporaryDirectory() as tmp:
            for extension in ('cjs', 'mjs'):
                script = Path(tmp) / ('cli.' + extension)
                script.write_text('#!/usr/bin/env node\nconsole.log("valid");\n')
                result = subprocess.run(['node', str(script)], capture_output=True, text=True, check=True)
                self.assertEqual(result.stdout.strip(), 'valid')
            package = Path(tmp) / 'package.json'
            package.write_text('{"type":"module"}')
            script = Path(tmp) / 'cli.js'
            script.write_text('#!/usr/bin/env node\nimport { strict as assert } from "node:assert"; assert(true);\n')
            subprocess.run(['node', str(script)], check=True)

    def test_json_recipe_in_bash_and_zsh_without_grep_p(self):
        recipe = fence('templates/skills/macos-rules/SKILL.md', 'For JSON, parse JSON:', 'bash')
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'package.json').write_text(json.dumps({'version': '2.0.0', 'other': '!=()'}))
            shells = ['bash'] + (['zsh'] if shutil.which('zsh') else [])
            for shell in shells:
                result = subprocess.run([shell, '-c', recipe], cwd=tmp, capture_output=True, text=True, check=True)
                self.assertEqual(result.stdout.strip(), '2.0.0')

    def test_drawio_path_with_spaces_is_data_not_command_substitution(self):
        recipe = fence('.claude/skills/drawio/SKILL.md', 'On WSL2, use', 'bash')
        result = subprocess.run(['bash', '-c', recipe + '\nprintf "%s" "$DRAWIO_CMD"'], capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout, '/mnt/c/Program Files/draw.io/draw.io.exe')
        self.assertEqual(result.stderr, '')

    def test_curl_failure_is_not_hidden_by_successful_parser(self):
        recipe = fence('patterns/agent-errors.md', 'For terse scripts:', 'bash')
        with tempfile.TemporaryDirectory() as tmp:
            for command, body in [('curl', 'exit 22'), ('jq', 'exit 0')]:
                path = Path(tmp) / command
                path.write_text('#!/bin/sh\n' + body + '\n')
                path.chmod(0o700)
            result = subprocess.run(['bash', '-c', recipe], env={**os.environ, 'PATH': tmp + os.pathsep + os.environ['PATH'], 'URL': 'https://unused.invalid'}, check=False)
        self.assertEqual(result.returncode, 22)

    def test_gh_fields_available_without_network(self):
        self.assertIsNotNone(shutil.which('gh'), 'gh is required for recipe validation')
        result = subprocess.run(['gh', 'pr', 'checks', '--help'], capture_output=True, text=True, check=True)
        fields = result.stdout.split('JSON FIELDS', 1)[1].split('LEARN MORE', 1)[0]
        for field in ['name', 'state', 'bucket', 'workflow']:
            self.assertRegex(fields, r'\b' + field + r'\b')
        self.assertIn('8: Checks pending', result.stdout)

    def test_python_project_pin_is_honored_offline(self):
        self.assertIsNotNone(shutil.which('uv'), 'uv is required for recipe validation')
        import sys
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / '.python-version').write_text(str(Path(sys.executable).resolve()))
            (Path(tmp) / 'pyproject.toml').write_text('[project]\nname="recipe-fixture"\nversion="0.0.0"\nrequires-python=">=3.10"\n')
            result = subprocess.run(['uv', 'python', 'find', '--offline', '--no-python-downloads'], cwd=tmp, capture_output=True, text=True, check=True)
            self.assertEqual(Path(result.stdout.strip()).resolve(), Path(sys.executable).resolve())


if __name__ == '__main__':
    unittest.main()
