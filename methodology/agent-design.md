# Agent Design Principles

## The Documentarian Rule

Every research-phase agent follows one absolute constraint:

> **Describe what EXISTS. Never suggest what SHOULD BE.**

This means:
- No improvement suggestions
- No problem identification
- No root cause analysis (unless explicitly asked)
- No code quality commentary
- No performance concerns
- No security warnings
- No refactoring recommendations
- No "better approaches"

**Why:** Research agents that mix observation with opinion produce noisy, biased output. Keeping them purely descriptive ensures the human gets clean, factual data to make their own decisions.

## Tool Restrictions by Role

| Role | Can Read/Search | Can Write/Edit | Can Run Shell | Can Access Web |
|------|:-:|:-:|:-:|:-:|
| Codebase Locator | Yes | No | No | No |
| Codebase Analyzer | Yes | No | No | No |
| Pattern Finder | Yes | No | No | No |
| Docs Locator | Yes (no deep reads) | No | No | No |
| Docs Analyzer | Yes | No | No | No |
| Web Researcher | Yes | No | No | Yes |
| Implementer | Yes | Yes | Yes | No |
| Reviewer | Yes | Yes (plan edits only) | Yes (tests only) | No |

**In Claude Code terms:** When spawning Task agents for research, instruct them to only use Glob, Grep, and Read tools. When spawning implementers, they get the full tool set.

## Subagent Prompting Best Practices

1. **Be specific about what to search for**, not how to search. The agent knows its tools.
2. **Specify the output format** you expect.
3. **Remind agents of the documentarian constraint** in every research prompt.
4. **Request file:line references** in every response.
5. **Spawn multiple agents in parallel** when they search for independent things.
6. **Wait for ALL agents** before synthesizing.
7. **Verify subagent results** — if something seems off, spawn a follow-up.

---

## Subagent Catalog

### Codebase Locator

**Purpose:** Find WHERE files live. A "super find/grep" — given a topic or feature, returns all relevant file paths grouped by purpose.

**Claude Code:** `Task` with `subagent_type: "Explore"`, prompt focused on finding file locations.

**Output:** Organized list of files by category (implementation, tests, config, types, docs) with full paths and counts.

**Does NOT:** Read file contents, analyze code, critique organization.

### Codebase Analyzer

**Purpose:** Understand HOW code works. Traces data flow, explains implementation, maps component interactions.

**Claude Code:** `Task` with `subagent_type: "Explore"`, prompt focused on reading and explaining specific files/components.

**Output:** Structured analysis with entry points, core implementation breakdown, data flow trace, patterns, configuration, and error handling — all with `file:line` references.

**Does NOT:** Suggest improvements, identify problems, comment on quality.

**Analysis strategy:**
1. Read entry points (exports, public methods, route handlers).
2. Follow the code path step by step.
3. Document the logic as-is.

### Pattern Finder

**Purpose:** Find EXAMPLES of similar implementations. Shows concrete code snippets that can serve as templates.

**Claude Code:** `Task` with `subagent_type: "Explore"`, prompt focused on finding similar patterns with code examples.

**Output:** Code snippets with file:line references, usage context, variations, and testing examples.

**Does NOT:** Recommend one pattern over another, identify anti-patterns, suggest improvements.

**Pattern categories to search:**
- API patterns (routes, middleware, errors, auth, validation, pagination)
- Data patterns (queries, caching, transformation, migrations)
- Component patterns (organization, state, events, lifecycle)
- Testing patterns (unit, integration, mocks, assertions)

### Docs Locator

**Purpose:** Find relevant historical documents (plans, research, tickets, decisions).

**Claude Code:** `Task` with `subagent_type: "Explore"`, prompt focused on finding markdown docs by topic.

**Output:** Categorized list of document paths with one-line descriptions.

**Does NOT:** Read documents deeply, analyze content.

### Docs Analyzer

**Purpose:** Extract HIGH-VALUE insights from historical documents. Aggressive filtering — only returns what's actionable and current.

**Claude Code:** `Task` with `subagent_type: "Explore"` or `subagent_type: "general-purpose"`.

**Output:** Document context, key decisions (with rationale), critical constraints, technical specs, actionable insights, open questions, relevance assessment.

**Filtering rules — include only if:**
- Answers a specific question
- Documents a firm decision
- Reveals a non-obvious constraint
- Provides concrete technical details
- Warns about a real gotcha

**Exclude if:**
- Just exploring possibilities
- Personal musing without conclusion
- Clearly superseded
- Too vague to act on
- Redundant with better sources

### Web Researcher

**Purpose:** Find external documentation, best practices, and solutions from the web.

**Claude Code:** `Task` with `subagent_type: "general-purpose"` using WebSearch and WebFetch tools.

**Search strategies by query type:**
- **API/Library docs:** Official docs first, then changelogs and release notes.
- **Best practices:** Recent articles from recognized experts, cross-reference multiple sources.
- **Technical solutions:** Specific error messages in quotes, Stack Overflow, GitHub issues.
- **Comparisons:** "X vs Y", migration guides, benchmarks.

**Output:** Summary, detailed findings organized by source with attribution and links, additional resources, gaps.

---

## Claude Code Extension Points

Beyond subagent prompting, Claude Code provides three mechanisms for extending agent capabilities. These map to different levels of the progressive disclosure hierarchy (see [context-engineering.md](context-engineering.md)).

### Skills (`.claude/skills/`)

Skills are on-demand knowledge files that Claude loads when relevant, without bloating every conversation. Use skills for domain knowledge, API conventions, and reusable workflows.

```
.claude/skills/
├── api-conventions/
│   └── SKILL.md          # REST API patterns for this project
├── database-patterns/
│   └── SKILL.md          # Query patterns, migration conventions
└── fix-issue/
    └── SKILL.md          # Workflow: analyze and fix a GitHub issue
```

**SKILL.md format:**
```markdown
---
name: api-conventions
description: REST API design conventions for our services
---
# API Conventions
- Use kebab-case for URL paths
- Use camelCase for JSON properties
- Always include pagination for list endpoints
```

**When to use skills vs CLAUDE.md:**
- Universal across ALL tasks → CLAUDE.md
- Relevant to specific task types → Skills
- Workflow with side effects the user triggers manually → Skill with `disable-model-invocation: true`

Invoke skills with `/skill-name` or let Claude auto-detect relevance from the `description` field.

### Custom Agent Definitions (`.claude/agents/`)

Define reusable subagent specs with their own tool restrictions and model selection. These formalize the subagent catalog entries above into Claude Code's native format.

```markdown
# .claude/agents/security-reviewer.md
---
name: security-reviewer
description: Reviews code for security vulnerabilities
tools: Read, Grep, Glob, Bash
model: opus
---
You are a senior security engineer. Review code for:
- Injection vulnerabilities (SQL, XSS, command injection)
- Authentication and authorization flaws
- Secrets or credentials in code
- Insecure data handling

Provide specific line references and suggested fixes.
```

This maps directly to the tool restriction table above — the `tools` field enforces what each agent can access. Use custom agents for recurring review patterns, specialized analysis, or any task that benefits from isolated context with constrained tools.

### Hooks

Hooks are deterministic scripts that run automatically at specific points in Claude's workflow. Unlike CLAUDE.md instructions (which are advisory), hooks are **guaranteed** to execute.

**Common hook patterns:**
- **Stop hook on file edit** — Run formatter/linter after every file change. Claude sees the errors and fixes them.
- **Stop hook on commit** — Run typecheck/lint before the commit is created.
- **Notification hook** — Alert when a long task completes.

**Hooks vs CLAUDE.md instructions:**
- "Always run lint after editing" in CLAUDE.md → Claude might forget. Use a hook.
- "Prefer small functions" → Advisory guidance stays in CLAUDE.md.

Configure hooks in `.claude/settings.json` or use the `/hooks` command. Claude can write hooks for you: "Write a hook that runs eslint after every file edit."
