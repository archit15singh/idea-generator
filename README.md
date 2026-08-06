# idea-generator

A founder-led idea factory, packaged as an OpenCode skill. The skill IS the DAG. Six subagents ARE the nodes. Deterministic gates between nodes live in code; agent reasoning lives in prose. The PM orchestrates dispatch, validates typed receipts, runs gates, and routes.

```
01 ingestor > 02 analyst > 04 scorer > 05 validator > 06 builder
                                                  > 07 clusterer (every 20 startups)
```

## Install

```sh
git clone https://github.com/archit15singh/idea-generator
cd idea-generator
python3 -m pip install --break-system-packages -e ".[test]"   # pydantic + pytest
cp -r skill      ~/.config/opencode/skills/idea-factory
cp    agents/*   ~/.config/opencode/agents/
cp    commands/idea-factory.md ~/.config/opencode/commands/

sqlite3 sid.db < skill/templates/schema.sql                  # idempotent
$EDITOR skill/templates/founder-profile.md                   # the scorer blocks on empty
```

Then in this session: `/idea-factory 5` to run a 5-startup cohort, or `/idea-factory <stage_marker>` to resume.

## What it does

Ingests YC companies in a constrained 20-market pool (3 ICP clusters, not 20 independent dimensions). For each startup: recursive L1-L10 descent (L5 is the wedge generator), 20+ wedge ideas with evidence citations, 8-axis fit scoring from your founder profile, top-wedge selection, 30 cold sends via gmail MCP, graduation only if reply rate ≥5% AND ≥3 pain-signal replies, instrumented MVP only on graduates, cross-cluster pattern promotion into a Pattern Library and Problem Graph with a fixed edge vocabulary.

## What's prose, what's code

Prose (reasoning, agents): SID extraction, recursive L1-L10, wedge ideation, fit judgment, outreach copy, pain classification, MVP construction, problem canonicalization.

Code (deterministic, gates): Pydantic types for every DAG edge, SQLite layer, `graduation_gate`, `evidence_gate`, `top_wedge`, `promotion_gate`, `kill_metric_triggered`, `classify_edge`, `builder_accepts`, receipt parsing. Agents cannot override these. They return `blocked` and a human edits.

## Layout

```
idea_factory/           Python package: typed contracts + determinism
  schema.py             Pydantic types for every node Input + Receipt
  db.py                 typed SQLite layer (idempotent upserts)
  decisions.py          deterministic gates living between nodes
  receipts.py           parse + validate agent JSON receipts

skill/
  SKILL.md              the orchestrator (this IS the DAG topology)
  references/workflows/  9 stage workflow prompts
  references/design/    13 design notes (the why)
  templates/schema.sql  idempotent SQLite schema
  templates/founder-profile.md  human input the scorer reads

agents/idea-factory-*.md  6 subagent definitions (prose reasoning)
commands/idea-factory.md  /idea-factory slash command

tests/test_80_20.py  34 crucial tests: schemas, gates, receipts, end-to-end
```

## Verify

```sh
python3 -m pytest tests/            # 34 passed
python3 -c "from idea_factory.db import DB; DB('/tmp/sid.db').init()"
```

## Kill metric

After 8 weeks of runtime, one wedge must have 3+ prospect replies indicating real pain. If `decisions.kill_metric_triggered(...)` returns `True`, the loop halts. Do not iterate on outreach copy. Re-tune `founder-profile.md`, re-descend, re-wedge, then resume.

## Honour rules

1. Validation before build. `decisions.builder_accepts` enforces it at the door.
2. No-evidence wedges die. `decisions.evidence_gate` rejects them between 02 and 04.
3. Pattern promotion needs 3+ sightings across 2+ of the 3 ICP clusters.
4. The scorer never overwrites a human-locked `personal_fit` row.
5. The Problem Graph uses the fixed edge vocabulary enforced by `decisions.classify_edge`.
6. The PM is the source of board truth. Subagents return receipts; gates route.