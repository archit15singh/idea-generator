# Personal Fit Score

Per-startup scoring across 8 axes. The point is not the number — it is **forced ranking** of where your existing unfair advantages compound.

## Axes (0–10 each)

| Axis | What "10" means |
|------|-----------------|
| Technical advantage    | You could ship v1 in a weekend. The stack is your home turf. |
| Interest               | You would work on it free for 6 months. |
| Existing knowledge     | You already know the market, jargon, and top 10 players. |
| Sales ability          | You can plausibly reach the economic buyer cold. |
| Long-term moat         | The wedge compounds (data, infra, network) rather than races to feature parity. |
| Build speed            | First value-delivering slice ships in days, not quarters. |
| Market size            | ≥$1B TAM or a credible expansion path to it. |
| Distribution fit       | You have an existing channel (audience, community, employer network) the buyer reads. |

`total` = sum (0–80). Store the per-axis values, not just the total — the shape matters more than the score (e.g., a 60 that is 10/10/2/8/10/10/2/8 is a build-fast-sell-it-yourself bet; a 60 that is 5/5/6/6/6/6/6/20-impossible... invalid).

## Rules

1. **Human-edited table, never auto-generated.** See `scraper-db-loader.md` — `personal_fit` is excluded from the loader's auto-regenerate set. The generator may propose a draft row, but the canonical row is reviewed before write.
2. **Score after the wedge list exists, not before.** You score fit for a *specific attack*, not for the startup. If a startup has 20 wedges, the startup gets one `personal_fit` row keyed to its most-selected wedge, with a note on which wedge it represents.
3. **Re-score quarterly.** Interest and distribution_fit drift fastest. Stale scores mislead the selection stage.

## Output

`INSERT OR REPLACE` into `personal_fit`. Per-axis columns are typed; `total` is computed on write, not hand-entered.