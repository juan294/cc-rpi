# Philosophy

## Core Tenets

1. **Research before you act.** Never modify code you haven't thoroughly read and understood. Every change begins with research.
2. **Plan before you implement.** Create explicit, phase-based plans with success criteria before writing a single line of production code.
3. **Human-in-the-loop at every gate.** The agent stops at phase boundaries and waits for human confirmation. No auto-proceeding.
4. **Documentarians, not critics.** During research, agents describe what *is* — they never suggest improvements, identify problems, or critique code quality unless explicitly asked.
5. **Automated verification first.** Manual testing is a last resort, reserved for cases that genuinely require human senses or privileges (sudo, hardware, visual UI validation).
6. **Atomic changes with review loops.** Implement, review, fix, approve, then move on. Never batch multiple unreviewed phases.
7. **Context is your only lever.** At every turn, a coding agent is a stateless function: context window in, next action out. The quality of the context window is the ONLY thing you can control to affect output quality.
8. **Specs are the new code.** Plans and research documents are the real "source code" of AI-assisted development. The generated code is more like a compiled artifact. Treat specs with the same rigor you'd treat source files.

## The Error Amplification Principle

Errors amplify as they move downstream through the pipeline:

```
A bad line of RESEARCH  →  thousands of bad lines of code
A bad line of a PLAN    →  hundreds of bad lines of code
A bad line of CODE      →  a bad line of code
```

Therefore: **focus human effort and attention on the HIGHEST LEVERAGE parts of the pipeline.** Review research more carefully than plans. Review plans more carefully than code. This is the single most important insight of the RPI pattern.

## This Is Not Magic

You must deeply engage with the output at every stage. If you kick off research and blindly accept it, or approve a plan without reading it, the entire pipeline falls apart. The RPI pattern makes performance *better*, but what makes it *good enough for hard problems* is that you build high-leverage human review into the pipeline at exactly the right points.

If research comes back wrong — throw it out and steer harder. If a plan misses the mark — iterate. The agent is a tool; the human is the quality gate.

## The Error Model

Errors in agentic coding trace to three root causes — all on the human side:

| Category | Examples |
|----------|----------|
| **Bad Prompt** | Ambiguous instructions, missing constraints, implicit expectations, no success criteria, wrong abstraction level |
| **Context Rot** | Conversation too long, stale context, overflow drowning signal |
| **Bad Harnessing** | Wrong agent type, subagent context loss, parallel when sequential needed, no guardrails, trusted without verification |

The model is the constant; the user's input is the variable. Improving at agentic coding means improving prompts, context management, and harness configuration.

## Mental Alignment

In teams, the most important function of the RPI workflow is not correctness — it's **mental alignment**. When AI writes most of the code, a much larger proportion of the codebase becomes unfamiliar. You can't read 2,000 lines of AI-generated code daily. But you *can* read 200 lines of a well-written implementation plan.

Research documents and plans become the primary mechanism for keeping team members on the same page about how the code is changing and why.

## Key Lessons

1. **Reading files fully before spawning subagents** prevents the orchestrator from decomposing the question incorrectly due to missing context.

2. **The "documentarian, not critic" constraint** is the single most impactful rule for research quality. Without it, agents produce noise.

3. **Separating locators from analyzers** prevents bloated, unfocused research results. Finding WHERE and understanding HOW are different cognitive tasks.

4. **The reviewer subagent in implementation** catches issues that the implementer misses. The reviewer can also add tests, which is a powerful quality mechanism.

5. **Phase gates with human confirmation** prevent runaway implementations that drift from intent. The cost of stopping is low; the cost of an incorrect multi-phase implementation is high.

6. **Maximum 3 clarification markers** in plans forces the planner to make informed decisions rather than deferring everything to the user.

7. **Explicit "What We're NOT Doing" sections** in plans prevent scope creep more effectively than any other mechanism.

8. **Context is the only lever.** Every agent turn is a stateless function call. The context window is literally the only input you control. Obsess over its quality.

9. **Errors amplify downstream.** A bad line of research becomes thousands of bad lines of code. Focus human review time on research and plans, not on generated code.

10. **Frequent intentional compaction is the core technique.** The entire RPI workflow is fundamentally a context management strategy.

11. **Subagents are context control, not role-playing.** The value of subagents is that they consume context in their window and return only the distilled result.

12. **Research on main, implement in worktrees.** Research and planning don't modify code, so they're safe on main. Implementation should happen in isolated branches.

13. **Multiple research passes are normal.** The first research pass may be wrong. Read it critically, and if it's off-base, throw it out and steer harder.

14. **You need a domain expert.** The RPI pattern amplifies expert knowledge — it doesn't replace it.

15. **Specs are the new code.** In AI-assisted development, the plans and research documents ARE the source code. Treat specs with the same rigor you'd treat source files.

16. **Deep engagement is required.** You must actively read and critically evaluate every research document and every plan. Blindly approving output defeats the entire purpose.
