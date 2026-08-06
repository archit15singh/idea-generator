# Startup Intelligence Database (SID), index

This is the entry point. The framework is split across focused files; each is independently runnable/reviewable.

## Data layer
- [`scraper-db-loader.md`](./scraper-db-loader.md), SQLite schema (idempotent init), scraper sources, loader contract. The persistence layer.
- [`generate-missing-wedges.md`](./generate-missing-wedges.md), ≥20 wedge types per startup; generation + evidence rules.
- [`generate-infrastructure-opportunities.md`](./generate-infrastructure-opportunities.md), "what internal platform did they build"; broader-applicability flagging.
- [`personal-fit-score.md`](./personal-fit-score.md), 8-axis scoring; human-edited, never auto-generated.

## Framing
- [`personalisation-and-founder-history.md`](./personalisation-and-founder-history.md), the 20 markets (as 3 ICP clusters) + founder-history inputs that feed the fit engine.

## Workflow
- [`factory.md`](./factory.md), continuous (no weekly cadence) 7-stage loop the agent runs; kill metric.
- [`structural-problems.md`](./structural-problems.md), three problems the factory must fix: validate before build, reply-rate honesty, MVP-as-survey.

## Reasoning
- [`recursive-framework.md`](./recursive-framework.md), 10-level descent per startup; L5 is the wedge generator, L7–L10 a concentration funnel.
- [`analysis.md`](./analysis.md), cross-cutting judgment calls, build sequence, TL;DR, open questions.

## Compound artifacts
- [`pattern-library.md`](./pattern-library.md), recurring abstractions = true output; promotion/retire rules.
- [`startup-intelligence-os.md`](./startup-intelligence-os.md), auto-ingest + generate + query; v0→v3 build sequence.
- [`problem-graph.md`](./problem-graph.md), reframe unit from startup to problem; controlled vocabulary + fixed edges.

---
Start with [`analysis.md`](./analysis.md) for the what-to-actually-do-first sequence.