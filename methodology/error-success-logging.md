# Error & Success Logging

## Success Logs

Most people only log failures. Logging successes helps identify what works and make it repeatable.

**When to log:** After a notably smooth task completion, first-try success, or elegant solution.

**Process:**
1. Review what went well in the conversation.
2. Ask 4-6 specific questions about WHY it worked (not generic "what went well").
3. Trace the exact triggering prompt that led to success.
4. Log with: what happened, why it worked, the exact prompt, contributing factors, reproducibility notes.

## Error Logs

The goal is to improve USER skill at agentic coding, not catalog model failures.

### Error Categories

**Prompt Errors:**
- Ambiguous instruction — could be interpreted multiple ways
- Missing constraints — didn't specify what NOT to do
- Too verbose — buried key requirements in walls of text
- Reference vs requirements — gave reference material, expected extracted requirements
- Implicit expectations — had requirements in head, not in prompt
- No success criteria — didn't define what "done" looks like
- Wrong abstraction level — too high-level or too detailed

**Context Errors:**
- Context rot — conversation too long, should have started fresh
- Stale context — old information polluting new responses
- Context overflow — too much info degraded performance
- Missing context — assumed the model remembered something it didn't

**Harness Errors:**
- Subagent context loss — critical info didn't reach subagents
- Wrong agent type — used wrong specialized agent for task
- No guardrails — didn't constrain agent behavior
- Parallel when sequential needed — launched agents with dependencies
- Missing validation — no check that agent output was correct
- Trusted without verification — accepted output without review

### Log Template Key Fields

- What happened (2-3 sentences)
- Primary cause (pick ONE category)
- The exact triggering prompt (verbatim)
- What was wrong with the prompt
- What the user should have said instead
- The gap: expected vs. got vs. why
- Prevention action items
- One-line lesson (actionable, about user behavior)

## Storage and Organization

### Where to Store Logs

Store logs as markdown files in your project's docs directory:

```
docs/
├── logs/
│   ├── errors/
│   │   └── YYYY-MM-DD-brief-description.md
│   └── successes/
│   │   └── YYYY-MM-DD-brief-description.md
│   └── README.md   # Index with one-line lessons
```

**Why markdown in git, not a database:**
- Logs are read by both humans and agents. Markdown is native to both.
- Git provides full history, blame, and search.
- Agents can read logs during research phases to avoid repeating known mistakes.
- No infrastructure to maintain.

### The Index File

Maintain a `docs/logs/README.md` with one-line lessons extracted from each log entry. This serves as a quick-reference for agents loading context:

```markdown
# Session Logs — Lessons Index

## Error Patterns
- Always scope API changes to specific endpoint paths (2025-12-15)
- Don't launch parallel subagents when they have dependencies (2025-12-18)
- Include success criteria in every implementation prompt (2026-01-03)

## Success Patterns
- Reference existing code patterns explicitly in prompts (2025-12-16)
- Constrain first phase to core functionality only (2025-12-20)
```

### When to Query Logs

- **Before `/research`**: Read the lessons index to prime the agent with known patterns.
- **Before `/plan`**: Check if similar features had error logs — avoid repeating mistakes.
- **After a session goes wrong**: Write the error log before closing the session, while context is fresh.
- **Periodically**: Review the index for recurring patterns. If you see 3+ entries about the same category, add a rule to CLAUDE.md or `patterns/quick-reference.md`.

### Graduating Logs to Rules

When a pattern appears 3 or more times in your logs:
1. Extract it as a rule in CLAUDE.md or `patterns/quick-reference.md`
2. Add a detailed entry to `patterns/agent-errors.md` if it's a Claude Code error
3. The log entries remain as historical evidence, but the rule becomes the primary reference

### Compression Over Time

**On success:** Successes are low-information events after extraction. The one-line lesson in the index is usually sufficient. Full success logs are historical reference.

**On failure:** Full error logs retain their value longer because root cause details matter. Don't compress error logs — they are the evidence base for pattern detection.
