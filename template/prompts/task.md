# Task prompt — give this to a worker

Fill the `<…>` parts (or let GitKeeper fill them) and paste into OpenCode, Copilot or Codex.

---

You are a worker agent in this repository. Read `AGENTS.md` first and follow it exactly.

**Your task is issue #<ISSUE_NUMBER>: <ISSUE_TITLE>**

<ISSUE_BODY — goal, acceptance criteria, files likely to change, expected proof>

Do this, in order:

1. Create branch `<feature|bugfix|upkeep>/<short-title>` from the latest `main`.
2. Turn each acceptance criterion into a test. Run them and confirm they fail. Commit.
3. Write the least code that makes them pass. Stay inside the listed files; if you
   must go outside, explain why in the PR.
4. Run the full test suite and linters locally. Run the feature yourself.
5. Open a PR with the template: `Closes #<ISSUE_NUMBER>`, and a **Verification**
   section with real proof (test output, the failing-then-passing test, screenshots).
6. **Stop.** Do not merge, do not start another task, do not edit guardrail files.

If anything in the issue is ambiguous, ask in the issue instead of guessing.
