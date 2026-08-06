---
description: Run the idea factory. Orchestrates ingestor, analyst, scorer, validator, builder, and clusterer subagents over a continuous loop with a kill metric.
---

Run the idea factory loop.

Arguments: $ARGUMENTS

Load the `idea-factory` skill (from `~/.config/opencode/skills/idea-factory/SKILL.md`) and follow the orchestrator contract there. Treat the arguments as either (a) a cohort size (e.g. "5") for the next ingestion batch, (b) a `stage_marker` to resume from (e.g. "resume from validated"), or (c) empty, meaning "advance one cohort from the next available stage."

Invariants: validation before build is non-negotiable; the scorer never overwrites a human-locked `personal_fit` row; the clusterer only promotes patterns with 3+ cross-cluster sightings and uses the fixed Problem-Graph edge vocabulary (`solves`, `sub-problem-of`, `suffers-from`, `enables`, `incumbent-of`, `OSS-alternative-to`); the kill metric (after 8 weeks, 1+ wedge with 3+ pain-reply signals) must be checked each loop pass and the loop halts if it fires.