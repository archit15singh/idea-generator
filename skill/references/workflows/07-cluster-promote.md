# 07 / Cluster + promote

After every cohort of 20+ newly-ingested startups, run pattern detection across the full DB. This is the system's compounding artifact. The SID is scaffolding; this is the product.

## 7.1 Cluster

Across all `startups` + `infrastructure_ops` + `wedges`:

- Group by underlying problem, not category label.
- Normalize before grouping using the controlled vocabulary in `references/design/problem-graph.md`. Resolve "AI memory" / "context retention" / "session memory" to one canonical problem-id.
- Cross-cluster count = number of distinct ICP clusters (A: developers, B: infra, C: enterprise-IT, per founder-history file) that contain an evidence row solving the same problem.

## 7.2 Promote to Pattern Library

Promote a category to a Pattern Library row only when the same normalized problem appears 3+ times across non-adjacent markets spanning 2+ of the 3 ICP clusters. Within-cluster repeats are noise; cross-cluster repeats are signal.

For each promoted pattern (`references/design/pattern-library.md`), write a mini-spec:

- incidental payers: which SID products bundle this pattern incidentally (cite startup_ids)
- OSS that exists: cite GitHub repos in the graph
- weak incumbent: cite min `moat` score in `startup_competitive` for the affected startups

Set `last_growth_rate` = (sightings now) − (sightings 30 days ago). Set `sightings` = current count. Set `retired_at` = NULL on promotion.

## 7.3 Update Problem Graph

- Insert new `problem_nodes` for promoted patterns.
- Insert `problem_edges` using the fixed edge vocabulary: `solves`, `sub-problem-of`, `suffers-from`, `enables`, `incumbent-of`, `OSS-alternative-to`. No free-form edges.
- For each wedge that graduated stage 06, write a `solves` edge from the wedge to the problem.
- For each interview finding from 6.4, write a `suffers-from` edge from the customer-complaint node to the problem.

## 7.4 Retire

A pattern whose `last_growth_rate <= 0` for 30+ days gets `retired_at` stamped. Saturated patterns are noise; keeping them pollutes the pattern library. Don't collect patterns you "should build". Collect patterns the data says recur.

## Output

- new rows in `pattern_library` (one canonical row per promoted pattern)
- new `problem_nodes` + `problem_edges` rows
- `retired_at` stamped on saturated patterns
- Each promoted pattern becomes a candidate spec for a new company

## Refs

- `references/design/pattern-library.md`, `references/design/problem-graph.md`, `references/design/analysis.md`