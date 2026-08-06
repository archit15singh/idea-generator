# 03 / Generate wedges + infrastructure ops per startup

Producer stage for ideas. Both tables are **derived** — delete-then-insert on regeneration. Stale rows are noise; never accumulate across runs.

## 3.1 Wedges (≥20 per startup)

For each of the 20 canonical wedge types (raw `generate-missing-wedges.md`), produce one row:

- `wedge_type` — controlled vocabulary (the 20)
- `description` — one sentence: **who suffers**, **why this wedge is sharper than the incumbent**, **what the MVP looks like in one phrase**. If the 1-sentence MVP is impossible, the wedge is too big → reject.
- `evidence` — must cite a `startup_competitive` or `startup_customer` field from the SID. **No evidence → reject the wedge.**
- `personal_fit_score` — NULL on first write; the next stage (`04`) fills it.

If a wedge type genuinely does not apply: write NULL `description` + a one-line "why not" — an explicit no-need row is a different signal from a missing row.

### The 20 wedge types

Smaller ICP · Different geography · Better UX · Open source · Self-hosted · Compliance-first · Cheaper · Faster · More accurate · AI-native · Vertical-specific · Developer-first · Enterprise-first · SMB-first · API-first · Offline/local-first · Mobile-first · Better integrations · Better memory · Better evaluation

## 3.2 Infrastructure opportunities

For each canonical internal platform (raw `generate-infrastructure-opportunities.md`), infer from the `startup_technical` row. Emit **only when the technical row demonstrates the forcing function**:

- `internal_platform` — controlled vocab
- `description` — *why* the product constraint forced the build (not just that it exists)
- `broader_applicability` — 0/1. Set 1 only with one explicit cross-market pairing (e.g., "this Memory applies to dev-tools + knowledge-mgmt because…").
- `evidence` — cite the `startup_technical` field

**If `startup_technical.memory` is NULL → do NOT emit Memory.** Absence is signal, not a gap to fill.

## Output

- `wedges` — UPSERT (delete-then-insert per startup per regen) keyed on `(startup_id, wedge_type)`
- `infrastructure_ops` — same
- `broader_applicability=1` rows are Pattern Library candidates (see `07-cluster-promote.md`)

## Refs

- raw `generate-missing-wedges.md` — wedge types and per-row fields
- raw `generate-infrastructure-opportunities.md` — internal-platform vocab and broader-applicability rules