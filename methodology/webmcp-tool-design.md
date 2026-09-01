# WebMCP Tool Design

> A tool a model can call is a spec, and every spec earns the same three passes: understand the real usage context, iterate the design against it, then verify against evidence.

WebMCP lets a page declare its own functionality to an agent at runtime. That declaration is a contract the model reads and acts on, which makes tool design a specification problem, not a coding problem. This document explains why the blueprint treats WebMCP as an extension of RPI rather than a separate framework to document in parallel, and maps where the pieces of that treatment live.

## What WebMCP Is and What It Is Not

WebMCP is a browser-native way for a page to declare its own functionality to an agent -- via `document.modelContext.registerTool` and related APIs -- replacing DOM scraping as the way an agent discovers what a page can do.

It is NOT a replacement for a server-side MCP server. The two answer different questions:

- **WebMCP** exposes what THIS page's current state and UI can do right now -- client-side, view-scoped, gone when the tab closes.
- **A server-side MCP server** exposes durable business operations independent of any particular page being open -- available whether or not a browser is involved at all.

This is the most common confusion about WebMCP, so state it plainly rather than assuming it's obvious: a WebMCP tool that "books the meeting" only exists while the booking page is open; a server-side tool with the same name exists whenever the server is up. Choose based on whether the capability depends on a page being open, not on which is more convenient to wire up.

## The RPI Isomorphism

Tool design for an agent has the same shape as any other spec: understand the actual usage context before designing, iterate the design against realistic scenarios before shipping, then verify against evidence rather than a single successful run. That is exactly RPI. The tool-design framework's own steps map onto it directly:

- **Research** -- "define the user goal" and "define the initial state." Before writing a tool, understand what the user is actually trying to accomplish and what the page looks like when they start.
- **Plan** -- "role-play the conversation" and "address variance." Walk the tool through realistic exchanges with a model, including the ways real users phrase things differently than the happy path, before committing to a signature.
- **Validate** -- "evaluate" and "deploy and observe." Run the eval corpus derived from the role-play, then watch real tool-call traces in production for drift the eval didn't cover.

Because this is the same shape as RPI, the blueprint doesn't need a fourth methodology alongside Research/Plan/Implement/Validate -- it needs the existing one applied to a new artifact type. That is why WebMCP tool design lives here, as a mapped extension, rather than as a standalone process with its own vocabulary.

## Where Each Piece Lives

Four surfaces carry this framework. A maintainer editing one should know what the others own:

- `methodology/webmcp-tool-design.md` (this file) -- why the framework works and how it maps onto RPI. Read once, by a maintainer or during `/bootstrap`.
- `templates/skills/webmcp/references/tool-design-framework.md` -- the executable step-by-step procedure. Ships downstream, opened on demand mid-task.
- `templates/skills/webmcp/SKILL.md` -- the tool contract itself, in wrong/right pairs.
- `templates/rules/webmcp.md` -- the one rule (adapter isolation) that must fire at edit time rather than on request.

## Rule #92

Role-play the conversation and ship an eval before shipping a tool to production.

Tool selection by a model is probabilistic, not deterministic -- the same tool, the same page state, and a slightly different phrasing of the user's request can produce a different call, a different set of arguments, or no call at all. A tool that works when you try it once by hand has not been shown to work; it has been shown to work once, under the one phrasing you happened to type. Only a role-play covering realistic variance, plus an eval corpus derived from that role-play, demonstrates that the tool holds up across the range of ways a real user's request reaches the model.
