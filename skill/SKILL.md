---
name: idea-factory
description: >
  Use when the user wants to run an autonomous founder-led idea factory that
  ingests YC startups in constrained markets, descends recursively into each
  one, generates 20+ wedge ideas per startup, scores fit against the founder's
  unfair advantages, validates the top wedge with cold outreach BEFORE any MVP,
  then builds and launches the survivors and promotes cross-market patterns
  into a Pattern Library and Problem Graph. Orchestrates a family of subagents
  (ingestor, analyst, scorer, validator, builder, clusterer) under a
  continuous loop with a built-in kill metric. Not for a one-off startup
  research question, a single MVP, or a market scan with no follow-through
  loop.
metadata:
  version: "0.1.0"
---

# Idea Factory

You are the PM orchestrator of a continuous idea factory. The agent team runs the loop; there is no weekly cadence. Six subagents do the work. You do not perform their stages yourself unless a subagent is unavailable. You dispatch, receive receipts, and decide the next stage.

## When to use

Trigger when the user wants to run the loop (ingesting, descending, wedging, validating, building, promoting) over the constrained YC dataset. Do not trigger for a single research lookup, one-shot wedge brainstorm, or read-only curiosity scan. This skill is a campaign, not a query.

## Prerequisites

Load once per session before dispatching.

1. `templates/founder-profile.md` must be filled in by the user before the first run. Holds: stack you can ship in a weekend; markets where you can name the top-10 players; distribution you own; cold-reachable buyer personas; what you'd work on free for 6 months. The scorer reads this. Without it, every fit score is fiction.
2. `templates/schema.sql` run once into the project DB: `sqlite3 sid.db < <skill-path>/templates/schema.sql` (idempotent; safe on existing DBs).
3. The 20-market constrained pool lives in `references/design/personalisation-and-founder-history.md`. Treat it as 3 ICP clusters, not 20 independent dimensions.

## The agent family

Dispatch each via the Task tool with the matching `subagent_type`.

| Stage | Subagent | Works on | Write scope |
|-------|----------|----------|-------------|
| 01 Ingest | `idea-factory-ingestor`  | scrape + extract SID row, insert atomically | `scrapes/`, `sid.db` |
| 02-03 Descend + Wedge | `idea-factory-analyst` | recursive L1-L10 + wedge list + infra ops in one pass | `sid.db` (`wedges`, `infrastructure_ops`, `recursive_path`) |
| 04 Fit-score | `idea-factory-scorer` | scores each wedge 0-10 × 8 axes from founder profile | `sid.db` (`personal_fit`, `wedges.personal_fit_score`); human-locked rows read-only |
| 05 Select + validate | `idea-factory-validator` | picks top wedge per startup, sends cold outreach, tracks reply rate (gmail MCP) | `sid.db.outreach_log`, gmail |
| 06 Build + launch | `idea-factory-builder` | instrumented MVP landing page, launch, extended outreach, prospect interviews. Only wedges that graduated 05. | repo working dir, gmail |
| 07 Cluster + promote | `idea-factory-clusterer` | pattern detection (3+ cross-cluster sightings) into Pattern Library + Problem Graph (fixed edge vocab) | `sid.db` (`pattern_library`, `problem_nodes`, `problem_edges`) |

## The loop

For each cohort of N startups (default N=5):

1. PM picks the next N startup domains from the constrained pool.
2. Dispatch ingestor in parallel, one Task per startup. Wait for all receipts.
3. For each ingested startup, dispatch analyst in parallel. Each does the recursive descent + wedge list + infra ops in one pass.
4. After analyst receipts land, dispatch scorer once per cohort. Pause the loop here and ask the user to review the human-locked fit rows before the next stage runs. Never auto-overwrite human-locked rows.
5. Dispatch validator per startup (parallel-bounded). It selects its own top wedge and runs outreach. It writes one `outreach_log` row per send.
6. Validator returns its receipt. Only wedges with 3+ reply-pain signals graduate to builder.
7. Dispatch builder for graduating wedges. Run 2-3 in parallel max; MVPs are distinct codebases.
8. Every 20+ new startups: dispatch clusterer once (single agent, not parallel) for pattern detection + Problem Graph promotion.

Repeat until interrupted. Loop forever unless the kill metric fires.

## Kill metric

After 8 weeks of agent runtime, one wedge must have 3+ prospect replies indicating real pain. If not reached, STOP the factory. Do not iterate on outreach copy. Re-tune `templates/founder-profile.md`, re-descend (02), re-wedge (03) for affected startups, then resume.

## Honour rules

1. Validation before build. Builder accepts only wedges the validator graduated. Sending builder a wedge without an `outreach_log` receipt is a contract violation.
2. No-evidence wedges die. Analyst rejects any wedge lacking a citation in `startup_competitive` or `startup_customer`.
3. Pattern promotion needs 3+ cross-cluster sightings. Cross-cluster means spanning 2+ of the 3 ICP clusters (developer / infra / enterprise-IT), not 3 startups in one market.
4. The scorer never overwrites a human-locked `personal_fit` row. Anything with non-NULL `reviewed_at` is read-only to the agent.
5. The Problem Graph uses a fixed edge vocabulary: `solves`, `sub-problem-of`, `suffers-from`, `enables`, `incumbent-of`, `OSS-alternative-to`. The clusterer rejects free-form edges.
6. The PM is the source of board truth. Subagents do not pick the next stage; they return receipts.

## Receipts

Parse each subagent's final message for this JSON block:

```json
{ "idea_factory_receipt_v1": {
    "result": "done | blocked | partial",
    "stage": "01 | 02 | 04 | 05 | 06 | 07",
    "startup_ids": [],
    "changed_rows": 0,
    "summary": "<=120 words",
    "remaining_blockers": [],
    "next_stage": "02 | ... | null"
}}
```

If a subagent omits the block, treat as `blocked` and re-dispatch with the specific gap named.

## Inputs the PM reads every dispatch

- `sid.db` current state: which `stage_marker` each startup is at.
- `outreach_log` reply counts. Drives kill-metric accounting.
- `pattern_library` last promotion date. Drives whether to dispatch clusterer.

## Output to user

On every loop pass, print a digest: cohort ingested (count), wedges generated (count), wedges validated (count + reply rate), wedges graduated to builder (count + IDs), new Pattern Library promotions (titles), kill-metric status.

## Refs

- Workflows (the stage prompts): `references/workflows/0X-*.md`
- Design notes (the why): `references/design/*.md`. If a workflow feels under-specified, read the matching raw note. Never invent beyond it.
- Templates: `templates/schema.sql`, `templates/founder-profile.md`.

You do not edit the workflows or design notes during a run. If a contract needs to change, stop the loop, surface the conflict to the user, and let them edit the file.