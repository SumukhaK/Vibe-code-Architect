# 1. Record technical decisions as ADRs

**Status:** Accepted

## Context
Agents and future-me need to know *why* a choice was made, not only what it is.
One ever-growing technical document becomes long, stale prose that agents
over-read and over-apply.

## Options
1. One large technical document.
2. One short file per decision (Architecture Decision Records).

## Decision
Option 2. `docs/TECHNICAL.md` holds only the current picture; each decision gets
a numbered file here: context, options considered, decision, consequences.

## Consequences
- A decision can be superseded by a newer ADR without rewriting history.
- Adding a new dependency or pattern requires an ADR in the same PR.
