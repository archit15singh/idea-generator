# 03 / Generate wedges + infrastructure ops

Producer stage for ideas. Both tables are derived. Delete-then-insert on regeneration. Stale rows are noise; never accumulate across runs.

## 3.1 Wedges (20+ per startup)

For each of the 20 canonical wedge types (`references/design/generate-missing-wedges.md`), produce one row:

- `wedge_type`: controlled vocabulary (the 20)
- `description`: one sentence. WHO suffers. WHY this wedge is sharper than the incumbent. WHAT the MVP looks like in one phrase. If the 1-sentence MVP is impossible, the wedge is too big: reject it.
- `evidence`: must cite a `startup_competitive` or `startup_customer` field. No evidence means reject the wedge.
- `personal_fit_score`: NULL on first write. The next stage (`04`) fills it.

If a wedge type genuinely does not apply: write NULL `description` plus a one-line "why not". An explicit no-need row is a different signal from a missing row.

### The 20 wedge types

Smaller ICP, Different geography, Better UX, Open source, Self-hosted, Compliance-first, Cheaper, Faster, More accurate, AI-native, Vertical-specific, Developer-first, Enterprise-first, SMB-first, API-first, Offline/local-first, Mobile-first, Better integrations, Better memory, Better evaluation.

## 3.2 Infrastructure opportunities

For each canonical internal platform (`references/design/generate-infrastructure-opportunities.md`), infer from the `startup_technical` row. Emit only when the technical row demonstrates the forcing function:

- `internal_platform`: controlled vocab
- `description`: why the product constraint forced the build, not just that it exists
- `broader_applicability`: 0/1. Set 1 only with one explicit cross-market pairing (e.g. "this Memory applies to dev-tools + knowledge-mgmt because...").
- `evidence`: cite the `startup_technical` field

If `startup_technical.memory` is NULL, do not emit Memory. Absence is signal, not a gap to fill.

## Output

- `wedges`: UPSERT (delete-then-insert per startup per regen) keyed on `(startup_id, wedge_type)`
- `infrastructure_ops`: same
- `broader_applicability=1` rows are Pattern Library candidates (see `07-cluster-promote.md`)

## Refs

- `references/design/generate-missing-wedges.md`: wedge types and per-row fields
- `references/design/generate-infrastructure-opportunities.md`: internal-platform vocab and broader-applicability rules