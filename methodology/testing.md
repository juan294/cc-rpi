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

## Verification Contract

Each plan phase should also define a compact **Verifier** section that
`/validate` can consume directly.

```markdown
### Verifier

- **Target behavior:** What should be true when the phase is complete
- **Automated checks:** Exact commands or inspections to run
- **Fixtures / data / setup:** Required inputs, seed data, or environment assumptions
- **Failure cases / edge conditions:** Specific cases the validator should inspect
- **Allowed manual exceptions:** Only the checks that truly cannot be automated, with WHY
```

The verifier is not a replacement for success criteria. It is the
compact contract that tells the validator what evidence to gather and
how to judge the phase.

When a repeated failure survives prose-only guidance, strengthen the
verifier with an executable check:

- add a **scripted verifier** when a command or inspection can detect
  the failure reliably
- add a **golden-case fixture** when the behavior needs a stable sample
  input/output pair or regression scenario

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
- **Repeated regressions should become golden cases.** If the same class
  of bug keeps returning, preserve the reproducer as a named fixture or
  representative sample, not just an ad hoc one-off test.

### In the RPI Workflow

TDD integrates into the Implement phase:
1. Plan specifies what each phase should accomplish
2. For each phase, write failing tests that capture the acceptance criteria
3. Implement until all tests pass
4. Run the full verification suite
5. Stop and wait for human review

The tests written in step 2 become the automated verification for the phase.

The phase verifier records the same intent in a compact, reusable
format so `/validate` can check the implementation against the plan
instead of relying on generic verification wording.

## Phase Completion Protocol

1. Run ALL automated verification commands.
2. Use tools to inspect outputs, API responses, file changes.
3. If all automated checks pass, mark phase complete.
4. **STOP. Wait for human confirmation.** Even if everything passes.
