# Change-request prompt — give this to the worker after a review

---

You are a worker agent in this repository. Read `AGENTS.md` first.

The reviewer requested changes on PR #<PR_NUMBER> (branch `<BRANCH>`).

<WORKER PROMPT from the reviewer's verdict block>

Do this:

1. Check out `<BRANCH>` and pull the latest commits. Do not create a new branch or PR.
2. For each requested change that alters behaviour, add or update a test first.
3. Make only the requested changes. Nothing else.
4. Run the tests and linters. Update the PR's **Verification** section with fresh proof.
5. Push to the same branch and reply on the PR with what you changed, point by point.
6. **Stop.**
