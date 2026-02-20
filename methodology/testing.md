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

## Phase Completion Protocol

1. Run ALL automated verification commands.
2. Use tools to inspect outputs, API responses, file changes.
3. If all automated checks pass, mark phase complete.
4. **STOP. Wait for human confirmation.** Even if everything passes.
