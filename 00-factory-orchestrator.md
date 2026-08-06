# Factory Orchestrator

You run the idea factory. The cadence is **continuous** — no week labels — because the agent is the executor. Each stage is one prompt; run them in order; batch where you can.

## Prerequisites (load once per agent session)

- `raw/personalisation-and-founder-history.md` — the constrained market pool (3 ICP clusters) + your founder-history profile (stack, cold-reachable buyers, what-you'd-do-for-free). Unlocks personal-fit scoring in stage 04.
- `raw/problem-graph.md` — controlled vocabulary of problem-IDs + fixed edge set. Required before any promotion in stage 07.

## Stages

1. `01-ingest.md` — scrape YC + website + GitHub; extract the SID row per startup; insert atomically. Batch-parallel across startups; one transaction each.
2. `02-descend-recursive.md` — recursive framework L1→L10 per startup. L5 is the only wedge-generating level; spend disproportionate time there.
3. `03-wedge-generate.md` — generate ≥20 wedge rows + N infrastructure-opportunity rows per startup. Both are derived tables — delete-then-insert on regeneration.
4. `04-personal-fit-score.md` — load founder history; score each wedge 0–10 × 8 axes. Human-locks first write; re-score quarterly.
5. `05-select-and-validate.md` — pick top wedge per startup; **validation gate BEFORE any MVP**. Reply rate is the single honesty metric.
6. `06-build-launch-outreach.md` — instrumented MVP, launch, outreach, prospect interviews. Only wedges that graduated stage 05 reach here.
7. `07-cluster-promote.md` — cross-market pattern detection; promote ≥3-cluster repeats to Pattern Library; update Problem Graph; retire zero-growth patterns.
8. `08-query-os.md` — answer natural-language queries over SID + Pattern Library + Problem Graph.

Stages 01–04 batch per startup. Stage 05 runs per wedge (parallel-bounded). Stages 06+ run only on validated wedges. Stage 07 runs periodically (every ≥20 new startups). Stage 08 runs on demand.

## Kill metric (terminate the loop, else it becomes a hobby)

After 8 weeks of agent runtime, ≥1 wedge must have **3+ prospect replies indicating real pain**. If not reached, STOP the factory. **Do not iterate on outreach copy.** Re-tune founder history (`raw/personalisation-and-founder-history.md`), then re-descend (02) and re-wedge (03) for affected startups.

## Honour rules

- **Validation before build.** (Structural problem #1, raw `structural-problems.md`.)
- **MVPs are surveys, not products** — but instrumented from line one. Uninstrumented MVPs produce no data; do not rebuild, re-extract.
- **The Pattern Library is a scoreboard, not a to-do list.** A "should-build" pattern with <3 cross-market sightings is retire-candidate noise.
- **Never auto-overwrite `personal_fit` rows** that a human has locked.
- **Reject any wedge with no evidence citation** in `startup_competitive` or `startup_customer`. No evidence → not selected.

## Refs

- All raw design files: `raw/*.md`. The workflow files consolidate them into prompts; the raw files hold the *why* behind each call when something feels under-specified.