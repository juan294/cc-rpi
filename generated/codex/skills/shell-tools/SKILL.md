---
name: "shell-tools"
description: "Shell and tool-call environment facts: escaping inside single-quoted zsh/jq/Python strings, complex regex in zsh, absolute paths and cwd resets between Bash calls, linter invocation, curl and JSON output handling, and choosing a built-in tool over a shell one-liner."
---

# Shell & Tools

Environment facts about the shell, the file tools, and the CLIs around them.
These do not become knowable through reasoning -- they are properties of zsh,
jq, Python, and the tool layer.

## Sequencing Fallible Calls

Run resource-intensive verification sequentially. Fail fast when later checks
need earlier success:

```bash
pnpm run typecheck && pnpm run lint && pnpm run test
```

To run every check, collect each status and return an aggregate failure:

```bash
result=0
pnpm run typecheck || result=$?
pnpm run lint || result=$?
pnpm run test || result=$?
exit "$result"
```

A bare `first; second` returns only the second command's status. A passing
last command must not hide an earlier failure. Sibling cancellation is a
harness-specific behavior, not a universal shell property.

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

Shell quoting and executable capabilities are separate. Single-quoted
patterns pass literally to bash and zsh. macOS BSD grep does not support
`-P`; wrapping it in `bash -c` does not add PCRE support.

For JSON, parse JSON:

```bash
python3 -c 'import json; print(json.load(open("package.json"))["version"])'
```

For plain text use `rg`, a supported `grep -E` pattern, or Python `re`.
Discover which executable is installed and check its help before using
nonportable flags. Use a script for complex parsing.

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

Or use the Glob tool. An unobserved path is unknown; only an actual filesystem check can establish
that it is missing.

### Re-read Before Bulk Operations

Wrong -- act on a file list captured several steps ago:

```bash
rm /tmp/out/a.json /tmp/out/b.json   # b.json already gone -> non-zero exit
```

Right -- inspect ownership and preserve unknown files before removal:

```bash
ls /tmp/out/
# Delete only explicitly identified, task-owned disposable files.
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

### Diagnose HTTP 403

403 means the server refused this request. Inspect the response for an
authentication, permission, resource-policy, rate-limit, or automation-block
reason. It does not prove every URL on the domain is blocked. Avoid blind
retries; retry only after a relevant correction or use an authorized alternate
source. See [HTTP semantics](https://www.rfc-editor.org/rfc/rfc9110.html#name-403-forbidden).

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

Right -- check transport and HTTP status before parsing:

```bash
response_file=$(mktemp) || exit 1
trap 'rm -f "$response_file"' EXIT
http_code=$(curl -sS -w '%{http_code}' -o "$response_file" "$URL") || exit $?
case "$http_code" in
  2??) jq '.[].id' "$response_file" ;;
  *) printf 'HTTP %s; inspect the saved response securely\n' "$http_code" >&2; exit 1 ;;
esac
```

For a terse pipeline use `set -o pipefail` and `curl -fsS "$URL" | jq '.'`.
Without `pipefail`, a successful parser can mask curl's failure. Avoid printing
response bodies containing credentials or private data. See [curl's manual](https://curl.se/docs/manpage.html).
