# Pattern Library

After ~100 startups, recurring abstractions surface — and these abstractions tend to be better businesses than any single application. The pattern library is the **true output** of the system; the SID rows are scaffolding.

## Seed categories (observed recurring primitives)

- **Memory** — repository · customer · meeting · personal
- **Evaluation** — LLM · agent · prompt · workflow
- **Observability** — agent tracing · AI debugging · cost tracking
- **Knowledge** — company brain · personal brain · research brain
- **Automation** — sales · support · engineering · compliance

These are seeds, not the final library. New patterns emerge from the `infrastructure_ops` table (`generate-infrastructure-opportunities.md`) and the Problem Graph (`problem-graph.md`).

## Three operating rules

1. **Promote a category to a pattern only after it appears ≥3 times across non-adjacent markets.** Within-market repeats are noise (everyone in "agent infra" needs memory). Cross-market repeats are signal.
2. **Each pattern gets its own mini-spec.** Which customers already pay for it *incidentally* (via a product that bundles it), which OSS exists, which incumbent is weak. The pattern's spec is what makes it fundable — not the pattern label.
3. **Re-evaluate monthly.** A pattern that stops growing is a saturated category, not an opportunity. Each pattern row carries a `last-growth-rate` timestamp and a ` sightings` count; a flat growth-rate after a month is a retire signal.

## The pattern is the scoreboard, not the to-do list

A pattern that crosses the 3× non-adjacent market bar becomes a **candidate spec** to build from. A pattern whose sightings flatten is a category to retire. Don't fill the library with things you "should" build — fill it with things the data says recur.