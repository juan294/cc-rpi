Validate the implementation against the plan.

Model tier: **sonnet** — Sonnet 4.6 (1M context) session.

Process:
1. Locate the plan (provided path or search recent git history).
2. Read the plan's phase files and extract each phase's **Verifier** section.
3. Gather evidence: git log, git diff, run test suites, inspect artifacts named in the verifier.
3. For each phase:
   - Verify marked-complete items are actually done.
   - Check the phase against the verifier's target behavior.
   - Run every automated verification command listed in the verifier.
   - Confirm fixtures/data/setup assumptions match reality.
   - Assess listed failure cases or edge conditions.
   - Confirm any manual exceptions are justified.
4. Generate a validation report with:
   - Implementation status per phase
   - Verifier results per phase
   - Automated verification results
   - Code review findings (matches, deviations, issues)
   - Manual testing required (only if automation impossible — explain WHY)
   - Recommendations
5. If code quality issues are found (reuse opportunities, inefficiencies,
   dead code), recommend running `/simplify` to fix them in one pass.
