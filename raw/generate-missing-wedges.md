# Generate Missing Wedges

For every startup, generate **≥20 wedges** — tight opportunities where the chosen startup is weak or absent. A wedge is a *smallest viable attack surface*, not a feature list.

## Canonical wedge types (the 20)

Smaller ICP · Different geography · Better UX · Open source · Self-hosted · Compliance-first · Cheaper · Faster · More accurate · AI-native · Vertical-specific · Developer-first · Enterprise-first · SMB-first · API-first · Offline/local-first · Mobile-first · Better integrations · Better memory · Better evaluation

One row per wedge type per startup. If a wedge type genuinely does not apply (rare), write a one-line "why not" instead of skipping — emptiness is signal, not absence.

## Per-wedge fields

- **wedge_type** — one of the 20 above (controlled vocabulary)
- **description** — the specific attack: *who* suffers, *how* the wedge is sharper than the incumbent, *what* the first MVP looks like in one sentence
- **evidence** — link to the section of the SID that justifies it (a weakness, a missing ICP, a pricing gap). No evidence → reject the wedge.
- **personal_fit_score** — 0–100, set by `personalisation-and-founder-history.md`, NOT by the generator
- **selected** — 0/1, set by the factory selection stage, not here

## Generation rules

1. **Tie every wedge to a Competitive weakness or Customer-pain field.** A wedge with no anchor in the SID is fiction.
2. **Specific over generic.** "Compliance-first" alone is noise. "SOC 2–first copilot for fintech SREs" is a wedge.
3. **≤1 sentence MVP.** If you cannot describe the MVP in one sentence, the wedge is too big — split it.
4. **Score honesty.** High personal_fit_score without a matching `personal_fit` table row → demote to 50.

## Output

Upsert into the `wedges` table (see `scraper-db-loader.md`), keyed on `(startup_id, wedge_type)`. Delete-then-insert per startup per regeneration — wedges are derived, stale wedges are noise.