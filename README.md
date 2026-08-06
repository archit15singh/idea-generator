# Idea Factory — execution workflows

Action-verb prompts; one MD per high-level step. Run them in order. The factory loops continuously — no weekly cadence — because the agent is the executor.

The detailed design notes that informed these prompts live in `raw/`. Consult them when a workflow file feels under-specified.

## Order

0. [`00-factory-orchestrator.md`](./00-factory-orchestrator.md) — glue, kill metric, what to run when
1. [`01-ingest.md`](./01-ingest.md) — scrape + extract SID row per startup (one transaction each)
2. [`02-descend-recursive.md`](./02-descend-recursive.md) — recursive framework L1–L10 per startup
3. [`03-wedge-generate.md`](./03-wedge-generate.md) — ≥20 wedges + infrastructure ops per startup
4. [`04-personal-fit-score.md`](./04-personal-fit-score.md) — load founder history; score each wedge 0–80
5. [`05-select-and-validate.md`](./05-select-and-validate.md) — pick top wedge per startup + prospect validation gate **before MVP**
6. [`06-build-launch-outreach.md`](./06-build-launch-outreach.md) — instrumented MVP, launch, outreach, interviews
7. [`07-cluster-promote.md`](./07-cluster-promote.md) — pattern detection, pattern library, problem graph promotion, retire stale
8. [`08-query-os.md`](./08-query-os.md) — natural-language queries over the OS

Read the orchestrator first. **Validation before build is non-negotiable** — it kills structural problem #1 (raw `structural-problems.md`).

## Raw design notes

All 13 design notes are in [`raw/`](./raw/):

- `SID.md` — original analysis index
- `scraper-db-loader.md`, `generate-missing-wedges.md`, `generate-infrastructure-opportunities.md`, `personal-fit-score.md`
- `personalisation-and-founder-history.md`, `factory.md`, `structural-problems.md`
- `recursive-framework.md`, `analysis.md`, `pattern-library.md`, `startup-intelligence-os.md`, `problem-graph.md`

They hold the *why* behind each call in the workflows. If a workflow disagrees with a raw note, the raw note is the source of truth — fix the workflow, do not edit the raw note unless the underlying principle changed.