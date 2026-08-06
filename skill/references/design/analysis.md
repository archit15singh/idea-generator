# Analysis, cross-cutting judgment calls

The judgment layered across the framework. Topic files say *what/how*; this file says *which calls matter and why*.

## The search-space constraint is the load-bearing decision

Constraining from 100 random startups to 20 markets reframes the project from **catalog** to **mental model**. The risk: the 20 are internally redundant, they are really ~3 ICP clusters × ~4 verticals, not 20 independent dimensions (`personalisation-and-founder-history.md`).

**Call:** accept the redundancy. Cross-market pattern transfer is the signal. But rename it honestly, "developer/enterprise-AI cluster", or expand to orthogonal markets later. Do not pretend independence.

## The recursion is asymmetric in value

L1–L4 are commodities. L5 ("what changed recently") is the only level that creates opportunity; everything else rearranges known supply (`recursive-framework.md`). **Disproportionate time belongs at L5.** L7–L10 are a concentration funnel, not alternatives; forcing L10 produces infra-for-its-own-sake.

## The pattern library is the product, the SID is scaffolding

Treat SID rows as scaffolding; the pattern library is the artifact that compounds (`pattern-library.md`). Three rules:

1. Promote to a pattern only after ≥3 occurrences across **non-adjacent** markets (within-market repeats are noise).
2. Each pattern gets a mini-spec: which customers pay for it incidentally, which OSS exists, which incumbent is weak.
3. Re-evaluate monthly. A "pattern" that stops growing is a saturated category to retire, not an opportunity.

## Build sequence for the Intelligence OS

Hand-fill 50 rows before any crawler; the schema will not survive contact with reality (`startup-intelligence-os.md`). Building v2 (query + clustering) before v0 is populated is the classic failure mode, the generator is trained on a moving target.

| Phase | What | Why |
|-------|------|-----|
| v0 (now)     | Hand-curated markdown/SQLite, ~50 rows       | Validate the schema. Fields churn on contact. |
| v1 (after 50) | Generated analysis with human review, OSS-only ingestion | Crawler on `ycombinator.com/companies`, LLM fill, human-locked edits. |
| v2 (after 200) | Cluster-by-problem + query layer             | Only worth it once patterns are detectable. |
| v3          | Problem Graph                                 | The strategic moat. |

## The Problem Graph is the single highest-value idea, and the easiest to fake

It reframes the unit from startup to problem and turns the project from a directory into a reasoning engine (`problem-graph.md`). Three cautions:

1. **Problems are fuzzy; name them deliberately.** "Persistent AI memory" ≡ "context retention across sessions." Build a controlled vocabulary / alias map early.
2. **Edges have meaning.** Fixed edge vocabulary: `solves`, `sub-problem-of`, `suffers-from`, `enables`, `incumbent-of`, `OSS-alternative-to`. Free-form edges → graph nobody can query.
3. **Sequence sources by ease:** startups → OSS → APIs → papers → complaints → job postings. Cross-source edges are the value; each source needs its own ingestion stub before edges can be drawn.

## What to actually do first

1. Lock the 20 markets as 3 ICP clusters.
2. Hand-fill 10 SID rows to validate the schema. Expect churn.
3. Stand up SQLite + markdown pipeline. Do not build the Intelligence OS yet.
4. After ~50 rows: start the Problem Graph with a controlled vocabulary + fixed edge set.
5. Re-run the Factory only with validation **before** the MVP (see `structural-problems.md`, `factory.md`).
6. The pattern library is a scoreboard, not a to-do list.

## Open questions before execution

- Which 2–3 markets from the 20 to start first? (Suggestion: AI Engineering, Agent Infrastructure, Technical Founder Tools, you are the ICP for all three.)
- Acceptable MVP failure mode, throwaway or shippable? Drives instrumentation.
- Where does the human-in-the-loop sit in the auto-analysis pipeline? Without a review gate, the SID fills with plausible fiction.
- What is the kill metric? "After 8 weeks, ≥1 wedge has 3+ prospect replies indicating real pain." Without one, the loop becomes a hobby.