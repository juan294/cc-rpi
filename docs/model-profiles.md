# Native Model Selection and Optional Profiles

RPI inherits the owner's active pane model and effort. Model profiles are optional
user configuration. The installer does not write global model settings, install a
statusline, launch a resolver service or change a running pane.

## Claude Code

Verified with Claude Code 2.1.261 on 2026-09-05:

```bash
claude --model best --effort high
```

This is an explicit research/planning launch. An implementation pane keeps the
owner's supported family selector and effort choice. For example, an owner who
chooses the Sonnet family can start that pane with `claude --model sonnet`.
`best` is a launch alias whose resolution depends on availability, not a pinned
provider generation. The CLI launch applies to that session. The interactive
`/model` command can also save a user default, so prefer launch flags when opening
independent panes. See [Claude model configuration](https://code.claude.com/docs/en/model-config).

For an explicitly selected mechanical task, `claude --model haiku` starts a
separate economy session when that family is available and adequate. The verified
Haiku capability does not advertise effort support; omit `--effort` for this
example. Hand off only the bounded task and return its result to the owner pane.
Do not classify architectural research, validation or stateful diagnosis as
mechanical by workflow name.

Default shared skills and subagents omit model/effort fields. Claude skill
frontmatter can override an explicit session selection, so RPI does not inject
automatic economy overrides. A CLI alias is not automatically valid in every
subagent schema. See the separate native [skill fields](https://code.claude.com/docs/en/skills)
and [subagent fields](https://code.claude.com/docs/en/sub-agents).

## Codex

Profiles are explicit, separate session launches. Select model IDs and supported
effort from the installed client's native catalog and your configuration. Catalog
defaults do not establish a quality ranking or prove account entitlement. Keep
concrete IDs in the dated adapter mapping rather than workflow bodies.

Codex 0.153.4 uses `codex --profile NAME` to layer a user-local
`$CODEX_HOME/NAME.config.toml` over the base configuration. Inspect the installed
client's `codex --help` before adapting older profile examples; do not assume
legacy `[profiles.NAME]` tables describe this version. The
[official profile documentation](https://learn.chatgpt.com/docs/config-file/config-advanced#profiles)
describes file layering; project and command-line settings have higher precedence.

The dated [adapter descriptor](../templates/adapters/model-profiles.json) contains
`clients.codex.profile_files` with three optional examples:

| User-local file under the configured Codex home | Explicit launch |
|---|---|
| `rpi-research.config.toml` | `codex --profile rpi-research` |
| `rpi-implementation.config.toml` | `codex --profile rpi-implementation` |
| `rpi-mechanical.config.toml` | `codex --profile rpi-mechanical` |

When choosing a profile, review the corresponding descriptor entry against your
current native catalog and account access. Manually put its selected `model` and
`model_reasoning_effort` values into that file as top-level TOML string keys.
Keep an existing file's unrelated settings and explicit choices. Research and
implementation profiles can express distinct owner choices; the shipped examples
start with the same primary selection. Profiles are not required to use RPI.

Model and effort overrides on a native Codex turn persist into subsequent turns.
Use a separate session for an explicitly selected economy task. Do not switch the
parent temporarily and claim automatic restoration. Claude frontmatter has no
Codex model-control meaning. If a native control is unavailable, inherit and
report the limitation.

## Evidence and Offline Behavior

Record requested role, requested model/effort and source, resolved values where
exposed, and evidence source/client version. A launch request is not an observed
model identity. Native observations must identify the current session and be
fresh; an unrelated pane, model prose, terminal title or newest rollout file is
not evidence for this pane.

In Claude session Bash, `CLAUDE_EFFORT` is an effort observation when present.
There is no assumed generic model-ID variable. Missing effort or model evidence
is unavailable. Offline catalog access leaves an explicit selection intact and
unresolved; it does not choose a fallback or claim a match.

## Read-Only Selection Report

From a verified source checkout or extracted package runtime root, inspect the
request without launching a model or writing configuration:

```bash
python3 templates/scripts/rpi-models.py --harness codex --role research --client-version 0.153.4
python3 templates/scripts/rpi-models.py --harness claude --role locator --client-version 2.1.261 --policy economy --mechanical
```

The first report contains no native overrides. The second describes an explicitly
selected mechanical economy request. `--model`, `--effort` and `--request-source`
record a specific owner choice; even a partial explicit choice takes precedence
without filling omitted fields from economy defaults. These commands describe a
selection and do not apply it.

For observed identity, use `--session-id` and `--observation` only with a captured
native event envelope from that session. The envelope identifies `source`,
`client_version`, `session_id`, timezone-qualified `observed_at` and native `data`.
The helper validates shape, session binding and freshness; it cannot authenticate
a caller's capture. Supported fields are filtered, and unrelated event data is
not included in the report. Missing, stale or mismatched evidence is unavailable.
