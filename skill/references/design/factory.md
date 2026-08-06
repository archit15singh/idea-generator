# The Factory (continuous, no weekly cadence)

The original was a Monday→Sunday cadence. That survives only if a human is the bottleneck. **The agent runs this workflow, so the cadence is "as fast as each stage completes"**, no day labels, no waiting for Friday to launch.

## Stages (run continuously, repeat per batch of startups)

1. **Research**, pick the next N startups from the constrained-20 pools, ingest via the scraper (`scraper-db-loader.md`).
2. **Extract**, for each, fill the SID: customer, problem, product, GTM, technical, competitive. Plus the wedge list (`generate-missing-wedges.md`) and infra ops (`generate-infrastructure-opportunities.md`).
3. **Select**, rank wedges by `personal_fit_score` (from `personal-fit-score.md`, seeded by `personalisation-and-founder-history.md`). Pick the top wedge per startup.
4. **Validate** *(before building)*, confirm the wedge exists for ≥1 real prospect. Cold outreach + reply-rate signal. This stage was missing from the weekly version and is required, see `structural-problems.md`.
5. **Build**, instrumented MVP for the validated wedge: landing page, waitlist, pricing-test variant. The MVP is a **survey**, not a product.
6. **Launch**, publish the landing page + outreach to the cohort.
7. **Interview**, prospect conversations; findings feed back into the SID and Problem Graph.

Stages 1–3 are batched (many startups in parallel). Stages 4–7 are per-wedge (one survivor at a time). They run as two coupled loops, not one.

## Annualized throughput (still the north star, now unconstrained by week boundaries)

~250 startups analyzed · ~100 wedges generated · ~50 MVPs · ~2,500 outbound · hundreds of conversations.

## Kill metric (terminates the loop, or it becomes a hobby)

After 8 weeks of runtime, **≥1 wedge must have 3+ prospect replies indicating real pain**. If not, wedge-selection is broken; stop and re-tune `personalisation-and-founder-history.md` before resuming. Without this, the agent maximises throughput, not learning.