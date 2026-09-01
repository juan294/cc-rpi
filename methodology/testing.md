# Testing Philosophy

## The Hierarchy

```
Automated (ALWAYS preferred)
├── Test suites (unit, integration, e2e)
├── Build commands
├── Type checking / linting
├── API response verification (curl, http tools)
├── File/output inspection
└── Code pattern verification (grep)

Manual (ONLY when automation is impossible)
├── Requires sudo/elevated privileges
├── Requires installing new software
├── Requires physical hardware interaction
└── Requires browser visual validation that truly can't be captured programmatically
```

## Verifying Probabilistic Surfaces

The hierarchy above assumes a check either passes or fails, and that running it once tells you the answer. That assumption breaks down for a surface whose caller is a model rather than a program: a WebMCP tool, an MCP server tool, a prompt with structured output. The same input can produce a different selection, a different set of extracted parameters, or a different response shape on two separate runs. The question stops being "did it pass" and becomes "how often, and how does it fail when it doesn't."

This does not apply to application code that merely runs near an LLM -- a request handler, a database write, a UI component -- those stay fully deterministic and belong in the hierarchy above, unchanged. It applies only where the thing making the decision under test is the model itself. If a check can be made deterministic, it is not an eval -- keep it in the automated suite above rather than routing it through this section.

### What an Eval Is Here

Fix the contract first: the input type, the output format, the constraints the response must satisfy. Only once the contract is fixed do a baseline result (what the surface does today) and an ideal result (what it should do) mean anything. An eval that skips straight to "does it work," without recording both a baseline and an ideal, is a vibe check, not an eval.

### What to Assert

Three things, run across multiple attempts or paraphrased inputs rather than eyeballed once:

- **Selection** -- did the model pick the right tool, path, or branch for the turn?
- **Extraction** -- did it pull the right values out of the conversation and available state?
- **State management** -- did the resulting sequence of calls respect the state transitions the surface expects?

A single passing run proves the happy path is reachable, not that it's reliable.

### How to Judge

Prefer a code-based check wherever the output is checkable -- schema validation, an exact-match assertion, a state readback. Reach for LLM-as-judge only where no deterministic check exists, such as judging whether free-text recovery guidance actually gives the caller something to do. This extends the hierarchy's automated-first preference one level up rather than replacing it: a deterministic check beats a model's opinion of its own output for the same reason it beats a human's.

### When an Eval Fails

Fix the surface, not the eval. Adjust the tool description, the prompt, or the schema that produced the wrong behavior. A special case bolted onto the eval to accommodate one bad run hides the defect instead of fixing it -- a surface that needs a carve-out per phrasing has a bad contract, not an eval with a missing exception.

See [rule #92](webmcp-tool-design.md#rule-92) for the concrete discipline -- role-play the conversation, then ship an eval derived from it -- that this section generalizes from.

## Success Criteria Format

Always separate into two sections:

```markdown
### Success Criteria

#### Automated Verification
- [ ] Tests pass: `npm test`
- [ ] Type check passes: `npx tsc --noEmit`
- [ ] Lint passes: `npm run lint`
- [ ] Build succeeds: `npm run build`
- [ ] API responds correctly: `curl localhost:3000/api/endpoint`

#### Manual Verification (only if truly impossible to automate)
- [ ] [Step] — WHY manual: [requires sudo / hardware / visual-only]
```

## TDD Protocol

Test-Driven Development is mandatory for all code changes. No exceptions — not even "small" changes.

### The Cycle

1. **Red** — Write a failing test FIRST, before touching any implementation code
2. **Green** — Write the minimum code to make the test pass
3. **Refactor** — Clean up while keeping tests green

### Rules

- **Tests before code, always.** If you catch yourself writing implementation without a test, stop and write the test first.
- **Bug fixes need a regression test.** Before fixing a bug, write a test that reproduces it. Then fix the code so the test passes. This ensures the bug never returns.
- **Refactors need existing tests.** Before refactoring, ensure tests cover the current behavior. If they don't, write them first.
- **No "I'll add tests later."** There is no later. Tests are written in the same worktree, in the same commit sequence, before the implementation.
- **Tests are the spec.** A failing test IS the specification for what the code should do. Write the test as if the feature already works, then make it true.

### In the RPI Workflow

TDD integrates into the Implement phase:
1. Plan specifies what each phase should accomplish
2. For each phase, write failing tests that capture the acceptance criteria
3. Implement until all tests pass
4. Run the full verification suite
5. Stop and wait for human review

The tests written in step 2 become the automated verification for the phase.

## Phase Completion Protocol

1. Run ALL automated verification commands.
2. Use tools to inspect outputs, API responses, file changes.
3. If all automated checks pass, mark phase complete.
4. **STOP. Wait for human confirmation.** Even if everything passes.
