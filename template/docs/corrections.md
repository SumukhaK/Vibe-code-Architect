# Corrections → rules

Every time an agent is corrected for a mistake that could happen again, it lands
here — and leaves as a check. The order is always:

1. **Rule** — a lint rule, type, test or architecture check that catches new
   occurrences (an `upkeep/` PR).
2. **Clean-up** — remove the old occurrences, so agents stop copying them.
3. **Verify** — make sure an agent can prove the right behaviour (test, screenshot,
   runtime check).

A correction that only ever becomes a sentence in `AGENTS.md` will be made again.

| Date | Mistake | Rule that now catches it | Clean-up PR | Verification |
| --- | --- | --- | --- | --- |
| | | | | |
