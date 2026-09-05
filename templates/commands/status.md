# Retired legacy status command

The legacy `/status` registration is discontinued because it collides with a
native harness command. Use the [rpi-status workflow](../skills/rpi-status/SKILL.md).

Claude direct invocation: `/rpi-status`. Claude plugin invocation:
`/cc-rpi:rpi-status`. Codex direct invocation: `$rpi-status` or the skill selector.
Use the actual installed plugin selector recorded by package diagnostics on Codex.

This file is migration documentation, never an installed command or forwarder.
Migration preserves a recovery copy and digest for a proven managed old command.
Unknown or customized commands are retained and reported rather than removed.
