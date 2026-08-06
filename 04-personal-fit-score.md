# 04 / Personal-fit score

**Do not auto-generate.** Load founder history first; project it onto the wedge. This stage is the human-in-loop gate — the generator may draft a row, but a human locks the canonical values.

## Inputs

- `raw/personalisation-and-founder-history.md` — your stack, markets you can name players in, distribution channels, cold-reachable buyer personas, what you'd do for free. **Load once per agent session.**
- `wedges` rows per startup (from stage 03)

## Do (one row per startup; one wedge-fit row per wedge later)

Score 0–10 across 8 axes (raw `personal-fit-score.md`):

| Axis | "10" means |
|------|----------|
| Technical advantage   | v1 ships in a weekend; stack is home turf |
| Interest              | you'd work free for 6 months |
| Existing knowledge    | you can name the top 10 players from memory |
| Sales ability         | you can plausibly reach the economic buyer cold |
| Long-term moat        | compounding (data, network, infra), not feature-parity race |
| Build speed           | first value-delivering slice in days, not quarters |
| Market size           | ≥$1B TAM or credible expansion path to it |
| Distribution fit     | you own a channel the buyer reads |

## Compute

`total` = sum 0–80. **Store per-axis values**, not just the total — shape > score. A 60 from `10/10/2/8/10/10/2/8` is a "build-fast-sell-it-yourself" bet; a 60 spread as `5/5/6/6/6/6/6/20-invalid` indicates a data-entry problem, not a strategy.

## Output

- `INSERT OR REPLACE` into `personal_fit` (one row per startup)
- Update `wedges.personal_fit_score` on each wedge — derived from the `personal_fit` of the startup weighted by wedge_type alignment with founder-history. The startup score is canonical; the wedge score is derived.
- Never auto-overwrite a row with a non-null `reviewed_at` — that is a human-locked row.

## Re-score rule

Quarterly. `interest` and `distribution_fit` drift fastest. Stale scores mislead the selection stage; flag rows older than 90 days.

## Refs

- raw `personal-fit-score.md`
- raw `personalisation-and-founder-history.md`