---
description: Contributing rules for cc-rpi -- adding error patterns, workflow docs, and consistency sweeps
paths:
  - patterns/**
  - methodology/**
  - templates/**
  - .claude/**
  - CLAUDE.md
  - AGENTS.md
  - README.md
  - GUIDE.md
  - CONTRIBUTING.md
  - CHANGELOG.md
---

# Contributing to cc-rpi

## Adding Error Patterns

When new error patterns are discovered during work on ANY project:

1. Add to `patterns/agent-errors.md` following the existing format
2. Add a one-liner to `patterns/quick-reference.md`
3. Update any hard-coded counts or references in onboarding docs and
   skills (`README.md`, `GUIDE.md`, bootstrap docs, `error-patterns/`)
4. Update `CHANGELOG.md`
5. Keep entries generic -- no project-specific references

## Adding Best Practices

When new best practices or methodology refinements are confirmed:

1. Add to the appropriate file under `methodology/`
2. Or create a new file under `patterns/` if it's a distinct topic

## Consistency Sweep for Workflow Changes

If a change touches workflow rules, topology guidance, commands, rules,
skills, hooks, or onboarding docs, sweep all documentation layers:

1. `methodology/`
2. `templates/`
3. Repo-local `.claude/` self-application
4. `CLAUDE.md` and `AGENTS.md`
5. `README.md` and `GUIDE.md`
6. `CHANGELOG.md`
