---
description: Run the PRE-BUILD idea factory (scout→ingest→analyse→score→select→optional validate→cluster). Never builds MVPs.
---

Run the idea factory **pre-build** loop. **Do not dispatch the builder.**

Arguments: $ARGUMENTS

Load the `idea-factory` skill (`skill/SKILL.md` or `~/.config/opencode/skills/idea-factory/SKILL.md`) and follow it. Prefer `pm.plan_recursive_fanout(db)` for the next parallel wave. Arguments: (a) cohort size for ingest only when plan allows, (b) `stage_marker` resume, (c) empty = advance one pre-build wave.

Invariants: **analyse drains before more ingest**; scorer never overwrites human-locked fit; clusterer needs 3+ cross-cluster sightings + fixed edge vocab; kill metric checked each pass; **stage 06 / idea-factory-builder is forbidden**.

Live board (Aug 07 2026): 142 startups (137 scored + 5 ingested) / 2740 wedges / 137 primary / personal_fit 137 / 16 patterns / segments 123 / candidates 277 / CANONICAL 27 / e2e 137/137 / next analyse (ids 146–150) — always re-plan via `plan_recursive_fanout`.