---
disable-model-invocation: true
---

# Legacy command renamed

This legacy command is a rename notice only. Its workflow is now `rpi-remediate`.

- Claude direct installation: invoke `/rpi-remediate`.
- Claude plugin installation: invoke `/cc-rpi:rpi-remediate`.
- Codex direct installation: invoke `$rpi-remediate` or select the skill.
- Codex plugin installation: use the actual selector recorded by package diagnostics.

Report this rename and stop. Do not auto-forward, bypass invocation controls or
execute an old workflow body. New installations do not add this legacy alias.
Existing managed aliases may retain this explicit-only notice during the 2.x
compatibility period; custom aliases remain user-owned.
