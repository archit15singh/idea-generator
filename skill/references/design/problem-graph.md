# The Problem Graph (the real moat)

> Startups come and go. Problems persist.

Reorganize the unit of the database from **startup** to **problem**. This is the single highest-value idea in the framework, and the easiest to fake.

## Structure

```
Problem
  ├── YC Startups
  ├── Open Source Projects
  ├── Academic Papers
  ├── Enterprise Vendors
  ├── APIs
  ├── Customer Complaints
  ├── Job Postings
  └── Emerging AI Capabilities
```

The graph answers "where *should* a new company exist?" instead of "which companies exist?". The SID is a side effect; the Problem Graph is the product.

## Three cautions

1. **Problems are fuzzy; name them deliberately.** "Persistent AI memory" and "context retention across sessions" sound different but are the same node. Build a **controlled vocabulary / problem-ID namespace + alias map** early, or the graph collapses into a pile of near-duplicate nodes. This is non-negotiable and must be done at v3 kickoff.
2. **Edges have meaning, not just "related to."** Fix a closed edge vocabulary:
   - `solves` · `sub-problem-of` · `suffers-from` · `enables` · `incumbent-of` · `OSS-alternative-to`
   Free-form edges produce a graph nobody can query.
3. **Node sourcing zuerst.** The value is in **cross-source edges** ("*this academic paper solves a sub-problem of an enterprise vendor's ICP complaint*"). Each source type needs its own ingestion stub before cross-source edges can be drawn. Sequence by ease:

   `startups → OSS → APIs → papers → complaints → job postings`

## Relationship to the rest of the system

- The Problem Graph is fed by the SID (`scraper-db-loader.md`) and the `infrastructure_ops` table (`generate-infrastructure-opportunities.md`).
- A *problem node* that accrues ≥3 cross-market `solves` edges graduates into the Pattern Library (`pattern-library.md`).
- The OS query layer (`startup-intelligence-os.md`) resolves natural-language queries against graph node IDs.

## Build order

Do not start the Problem Graph before v0 (the SID) has ~50 manually-shaped rows. The **controlled vocabulary of problem IDs** is the artifact that takes longest to get right and that compounds longest once correct. Start it once, names it deliberately, alias aggressively, and never let auto-naming overwrite a human-canonical node.