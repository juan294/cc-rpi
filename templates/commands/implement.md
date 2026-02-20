Implement the plan at: $ARGUMENTS

Process:
1. Read the plan completely. Check for existing checkmarks.
2. Spawn Explore agents to gather relevant context.
3. Create tasks (TaskCreate) to track progress.
4. For the CURRENT phase only:
   a. Delegate implementation to subagents (up to 3).
   b. When done, submit to a reviewer subagent.
   c. If reviewer requests fixes, send back to implementer.
   d. Repeat until reviewer approves.
   e. Run ALL automated verification commands.
   f. Update checkboxes in the plan file.
5. STOP. Report results and wait for human confirmation.
6. Do NOT proceed to the next phase without confirmation.

If plan doesn't match reality:
- STOP and present: Expected vs Found vs Why it matters.
- Ask how to proceed.
