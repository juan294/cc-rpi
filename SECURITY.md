# Security Policy

## Scope

This repository contains methodology documentation, operational patterns, and templates. It does not contain executable software or services. However, the templates and patterns influence how agents operate in real projects, so security matters.

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.x     | Yes       |

## Reporting a Vulnerability

If you discover a security issue — for example, a pattern or template that could lead agents to expose secrets, bypass safety checks, or create insecure code — please report it responsibly.

**Do not open a public issue.**

Instead, use [GitHub's private vulnerability reporting](../../security/advisories/new) to submit your report.

Please include:
- A description of the issue
- Which file(s) are affected
- The potential impact
- Steps to reproduce (if applicable)

You should receive a response within 7 days. We will work with you to understand the issue and coordinate a fix.

## What We Consider Security Issues

- Templates or patterns that could cause agents to leak secrets (API keys, tokens, credentials)
- Instructions that could lead to unintended code execution
- Patterns that bypass safety validations or pre-commit hooks
- Configurations that weaken git security (e.g., `--no-verify` by default)
