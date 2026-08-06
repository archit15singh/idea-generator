# 05 / Select + validate

Pick the top wedge per startup by fit. Verify the wedge exists for a real prospect before any MVP gets built. This stage is the factory's honesty check (`references/design/structural-problems.md`).

## 5.1 Select

For each startup, query `wedges` joined with `personal_fit`, weighted:

- `personal_fit.total × 0.6`
- evidence tightness × 0.4 (a wedge with no `startup_competitive`/`startup_customer` citation gets evidence=0 and is auto-disqualified)

Pick top-1 wedge per startup. Mark `wedges.selected=1`. Reject ties with no evidence. Do not soft-rank fiction.

## 5.2 Validate (before any MVP)

For every selected wedge with `personal_fit.total >= 60`:

1. Generate 30 cold-outreach messages, varied in opener + pain-hypothesis, personalized by persona (not template-blasted).
2. Send to plausible economic buyers from the cold-reachable list in `templates/founder-profile.md`.
3. Track reply rate. This is the single honesty metric.

## 5.3 Gate

| Signal | Action |
|--------|--------|
| Reply rate 5%+ across cohort | wedge graduates to `06-build-launch-outreach.md` |
| <5% across 30+ messages | wedge-selection is broken. Do not iterate on outreach copy. Re-tune founder history, then re-descend (02) and re-wedge (03) for affected startups. |
| 3+ replies indicating real pain within 8 weeks | kill metric sustained (`references/design/analysis.md`); factory keeps running |

## Output

- updated `wedges.selected` column
- new `outreach_log` rows (startup_id, wedge_id, sent_count, reply_count, replied_at, reply_pain_signal 0/1)

## Honour rule

A wedge with high `personal_fit.total` but reply-rate <5% after 30 messages is not outreach-broken. It is wedge-selection-broken. Don't patch copies.

## Refs

- `references/design/structural-problems.md`, `references/design/factory.md`, `references/design/analysis.md`