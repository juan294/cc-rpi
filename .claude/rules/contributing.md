---
description: Contributing rules for cc-rpi -- adding error patterns, rules, methodology refinements
paths:
  - patterns/**
  - methodology/**
  - templates/**
---

# Contributing to cc-rpi

## Adding Error Patterns

When new error patterns are discovered during work on ANY project:

1. Add to `patterns/agent-errors.md` following the existing format
2. Add a one-liner to `patterns/quick-reference.md`
3. Update counts in `GUIDE.md`
   (two locations: prose paragraph + "Where to Go Deeper" table)
4. Update `CHANGELOG.md`
5. Keep entries generic -- no project-specific references

## Adding Best Practices

When new best practices or methodology refinements are confirmed:

1. Add to the appropriate file under `methodology/`
2. Or create a new file under `patterns/` if it's a distinct topic
