---
description: Run the PRE-BUILD idea factory (scout→ingest→analyse→score→select→optional validate→cluster). Never builds MVPs.
---

Run the idea factory **pre-build** loop. **Do not dispatch the builder.**

Arguments: $ARGUMENTS

Load the `idea-factory` skill (`skill/SKILL.md` or `~/.config/opencode/skills/idea-factory/SKILL.md`) and follow it. Prefer `pm.plan_recursive_fanout(db)` for the next parallel wave. Arguments: (a) cohort size for ingest only when plan allows, (b) `stage_marker` resume, (c) empty = advance one pre-build wave.

Invariants: **analyse drains before more ingest**; scorer never overwrites human-locked fit; clusterer needs 3+ cross-cluster sightings + fixed edge vocab; kill metric checked each pass; **stage 06 / idea-factory-builder is forbidden**.

Live board (Aug 07 2026): 396 scored / 7920 wedges / 396 primary / personal_fit 396 / 104 patterns / CANONICAL 32/32 / e2e 396/396 / next ingest — always re-plan via `plan_recursive_fanout`.