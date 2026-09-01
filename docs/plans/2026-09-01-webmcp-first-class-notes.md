# Deviation Log: webmcp-first-class

`/validate` reads this file. Deviations only -- no narration.

## Phase 1

- Plan said: `methodology/webmcp-tool-design.md` alone carries "What WebMCP
  Is and What It Is Not" -- the client-page-scoped-vs-server-side-MCP
  distinction -- per phase-1.md's content brief for that file.
- Found: `methodology/` ships to no downstream project and is read once at
  authoring time (the file's own "Where Each Piece Lives" section says so).
  Neither `SKILL.md` nor `references/tool-design-framework.md` -- the two
  surfaces that actually ship and fire when an agent is designing a tool
  set -- stated this distinction anywhere.
- Chose: added one paragraph to `SKILL.md`'s "The API Surface" section
  restating the boundary (a WebMCP tool is page-scoped and vanishes when
  the tab closes or its controller aborts; a durable capability is a
  server-side MCP tool instead), in addition to the fuller treatment that
  stays in `methodology/webmcp-tool-design.md`.
- Why: the distinction only matters at the moment an agent designs a tool
  set, which is exactly when `SKILL.md` fires. Leaving it solely in a
  maintainer-only file made the framework's most load-bearing scoping
  judgment unreachable at the one moment it's needed. Surfaced by the
  `/simplify` altitude-angle review.
