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
