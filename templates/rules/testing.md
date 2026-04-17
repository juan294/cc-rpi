---
description: TDD protocol and testing philosophy -- red-green-refactor, regression tests, verification hierarchy
paths:
  - "**/*.test.*"
  - "**/*.spec.*"
  - "**/test/**"
  - "**/tests/**"
  - "**/__tests__/**"
  - vitest.config*
  - jest.config*
  - pytest.ini
  - pyproject.toml
---

# Testing

## TDD Protocol

All code changes follow Red-Green-Refactor:

1. **Red** -- Write a failing test FIRST
2. **Green** -- Minimum code to pass
3. **Refactor** -- Clean up with green tests

No exceptions. Bug fixes need a regression test.
Refactors need existing coverage. No "tests later."

## Verification Sequencing

Run checks sequentially, never as parallel Bash calls
(hook enforced). Chain: `typecheck ; lint ; test`

## Phase Verifier

Each plan phase should include a compact verifier section so the
validator knows:

1. What target behavior to confirm
2. Which automated checks to run
3. Which fixtures or setup assumptions matter
4. Which edge cases to inspect
5. Which manual exceptions are allowed, with WHY
