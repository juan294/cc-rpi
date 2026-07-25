---
name: shell-tools
description: "Shell and tool-call environment facts: escaping inside single-quoted zsh/jq/Python strings, complex regex in zsh, absolute paths and cwd resets between Bash calls, linter invocation, curl and JSON output handling, and choosing a built-in tool over a shell one-liner."
---

# Shell & Tools

Environment facts about the shell, the file tools, and the CLIs around them.
These do not become knowable through reasoning -- they are properties of zsh,
jq, Python, and the tool layer.

## Sequencing Fallible Calls

Wrong -- independent Bash calls issued in parallel; one failure kills all siblings:

```bash
# Parallel call 1: pnpm run typecheck
# Parallel call 2: pnpm run lint
# Parallel call 3: pnpm run test
```

Right -- chain sequentially so each result survives:

```bash
pnpm run typecheck 2>&1 ; pnpm run lint 2>&1 ; pnpm run test 2>&1
```

Use `&&` when a later step is meaningless after an earlier failure, `;` when
you want every result regardless.

## Quoting and Escaping

Inside single quotes, every character is literal. Escaping an operator there
inserts a real backslash into the string and breaks the consumer.

Wrong -- backslash reaches jq and Python as data:

```bash
jq '.[] | select(.name \!= "review")'   # jq: INVALID_CHARACTER
python3 -c 'assert x \!= y'             # SyntaxError
```

Right -- write the operator plainly inside `'...'`:

```bash
jq '.[] | select(.name != "review")'
python3 -c 'assert x != y'
```

### Complex Regex in zsh

Wrong -- zsh treats `!`, `{`, and `}` specially before the command ever runs:

```bash
grep -oP '(?<=version":")[^"]+' package.json
# zsh: event not found
```

Right -- use the built-in Grep tool, a dedicated linter, or wrap in bash:

```bash
bash -c 'grep -oP '"'"'(?<=version":")[^"]+'"'"' package.json'
```

Reach for the built-in Grep tool first. It takes the pattern as data, so no
shell parsing happens at all.

## Paths

The file tools do not expand `~`, and the shell's working directory resets
between Bash calls.

Wrong -- tilde in a file tool, relative path across calls:

```text
Read("~/code/project/src/index.ts")     # no such file
```

```bash
cd ../other-project && pnpm test        # cwd already reset; ../ is wrong
```

Right -- absolute paths everywhere, and `cd` inside the same call:

```text
Read("/Users/you/code/project/src/index.ts")
```

```bash
cd /absolute/path/to/other-project && pnpm test
```

### Do Not Fabricate Paths

Plausible-sounding directory names (`Projects`, `repos`, `workspace`) are
guesses. Discover the path instead:

```bash
pwd
ls /absolute/path/to/parent
```

Or use the Glob tool. A path you did not observe is a path that does not exist.

### Re-read Before Bulk Operations

Wrong -- act on a file list captured several steps ago:

```bash
rm /tmp/out/a.json /tmp/out/b.json   # b.json already gone -> non-zero exit
```

Right -- list first, or make the removal tolerant:

```bash
ls /tmp/out/
rm -f /tmp/out/*.json
```

## Choosing the Tool

### Run `--help` Before Guessing Flags

Each CLI has its own flag vocabulary. `--json` works on `gh` and not on
`vercel`; `--notes` works on `gh release create` and `--body` does not.

```bash
vercel deploy --help 2>&1 | head -30
```

### Write a Script Instead of a Mega One-Liner

Wrong -- a single command carrying loops, `awk`, and nested quoting:

```bash
for f in $(find . -name '*.md'); do awk '/^##/{c++} END{print FILENAME, c}' "$f"; done
```

Right -- write it to a file and run it, or use the built-in tools:

```bash
# Prefer Grep / Glob / Read when they answer the question.
# Otherwise:
cat > /tmp/count-headings.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
...
EOF
bash /tmp/count-headings.sh
```

Built-in Grep, Glob, and Read avoid shell quoting entirely and return
structured results.

### Linters Take Only Their Own File Types

Wrong -- `markdownlint` pointed at a shell script produces confident nonsense:

```bash
npx markdownlint '**/*' 2>&1
```

Right -- scope the glob, and use `--fix` before hand-editing:

```bash
npx markdownlint '**/*.md' --ignore node_modules 2>&1
ruff check --fix .        # "[*]" in ruff output means auto-fixable
eslint --fix .
```

Before "fixing" a warning, check whether the pattern is intentional. Add a
linter exception rather than changing correct content.

### A 403 From WebFetch Is Not Transient

A 403 means the domain blocks automated requests. Retrying, or trying an
alternate path on the same domain, returns 403 again. Switch strategies: use
WebSearch, or ask for the content directly.

### Create Boilerplate Files Sequentially

API content filters can block certain filenames (`CODE_OF_CONDUCT.md`,
`SECURITY.md`) mid-batch. Creating them one at a time with a fallback keeps a
single block from wasting the whole turn.

## JSON and HTTP Output

### Inspect Structure Before Indexing

Wrong -- assume the shape:

```python
data['results'][0]        # TypeError: list indices must be integers
```

Right -- look first:

```python
print(type(data))
print(data[:1] if isinstance(data, list) else list(data)[:5])
```

### Save curl Output Before Parsing

Wrong -- pipe straight into a parser; an HTML error page or auth failure
produces an unhelpful parse error instead of the real problem:

```bash
curl https://api.example.com/things | jq '.[].id'
```

Right -- capture the response and check the status:

```bash
curl -sS -w '%{http_code}' -o /tmp/resp.json https://api.example.com/things
head -c 200 /tmp/resp.json
jq '.[].id' /tmp/resp.json
```

`curl -sf` is the terse form: it fails the pipeline on an HTTP error instead
of emitting the error body.
