# Idea Factory E2E Live Run

## Objective

Execute the idea-factory skill's e2e workflow for a live cohort: market scout (00) → ingestor (01, real web extraction) → analyst (02, recursive descent + 20+ evidence-backed wedges) → scorer (04) → validator (05) → builder (06) → clusterer (07), using the idea-factory subagents and running every deterministic gate in code. The emphasis is a genuine **live web run** of extraction + idea generation, not a replay of the existing synthetic DB data.

## Original Request

"Execute the skill and run the e2e workflow, use idea factory agents and execute the agents to do the actual e2e flow of extracting and idea generation e2e live run web."

## Intake Summary

- Input shape: `existing_plan` (the skill IS the DAG; agents installed; code gates verified, 41 tests pass)
- Audience: the user (founder / idea-factory operator)
- Authority: `requested`
- Proof type: `artifact` + `metric` (sid.db rows, receipts, gate results)
- Completion proof: a live cohort flows through scout → ingestor (real SID extracted from live web) → analyst (20+ wedges passing `evidence_gate`), with every stage verified by code gates and every task carrying a receipt; further stages (scorer/validator/builder/clusterer) advance as far as their preconditions allow, each blocked-with-receipt or approved by the user.
- Goal oracle: sid.db advancing via live web — `candidate_startups` populated by the scout, startups with real SID sections and `stage_marker='ingested'`, wedges with citations passing `evidence_gate`, receipts on every task.
- Likely misfire: the run "succeeds" by replaying the existing synthetic DB (placeholder wedges, fake outreach) instead of doing a live web extraction; agents fabricate evidence to pass gates; the run stops at planning/selection.
- Blind spots considered:
  - `founder-profile.md` is EMPTY → the scorer blocks; will hit a human-input gate at stage 04.
  - Validator sends real cold email (30/persona) and Builder launches real MVPs → real-world side effects, require explicit user approval and gmail pairing.
  - Existing DB holds 5 synthetic startups with placeholder wedges and fake outreach; re-ingesting/re-analysing them with live web data is the correct way to get real data (idempotent upserts).
  - Web scraping may time out; accept 404s per the ingestor's best-effort rule.
- Existing plan facts:
  - DAG entry is non-negotiable: start from `pm.default_scout_input()`, dispatch the market scout, fan out on candidates.
  - Dispatch via Task tool with typed inputs from `idea_factory.pm`; validate receipts with `idea_factory.receipts.parse`; route with `idea_factory.decisions`.
  - Honour rules: validation before build; no-evidence wedges die; scorer never overwrites human-locked `personal_fit`; clusterer uses fixed edge vocabulary; PM owns board truth.
  - Do not edit `schema.py`, `db.py`, `decisions.py`, `receipts.py`, `agents/*.md`, or design notes during the run.

## Goal Oracle

`A live cohort reaches stage_marker='analysed' with real SID rows and 20+ evidence-cited wedges per startup, produced by idea-factory agents from live web fetches, with receipts and gate outputs on every task.`

The PM must keep comparing task receipts to this oracle. Replaying synthetic data, skipping the market scout, or stopping after planning/selection does not count.

## Goal Kind

`existing_plan`

## Current Tranche

Continuous execution of the e2e DAG for one live cohort, bounded to a safe number of candidates the first pass. After the analyst stage, continue through scorer (blocked on empty founder profile unless the user fills it), validator and builder (blocked on real-world side-effect approval), and clusterer (runs when the cohort reaches ~20 startups). Final audit maps all receipts back to the original outcome.

## Non-Negotiable Constraints

- The DAG starts from `pm.default_scout_input()` — never from a flat startup list.
- Every agent receipt is parsed with `idea_factory.receipts.parse`; routing decisions come only from `idea_factory.decisions`.
- The scorer never overwrites a human-locked `personal_fit` row.
- Validation before build (`decisions.builder_accepts`); no-evidence wedges die (`evidence_gate`).
- No edits to `schema.py`, `db.py`, `decisions.py`, `receipts.py`, `agents/*.md`, or design notes during the run.
- Real cold-email sends and MVP launches require explicit user approval; the scorer requires a non-empty `founder-profile.md`.
- Kill metric (`decisions.kill_metric_triggered`) checked each validator pass; halt if it fires.

## Stop Rule

Stop only when a final audit proves the full original outcome is complete (live extraction + idea generation achieved, receipts on all tasks, further stages blocked/approved with receipts). Do not stop after planning or Judge selection. Do not stop because a slice needs owner input (founder profile, email approval) — block that exact task with a receipt and continue every safe local stage.

## Slice Sizing

A good Worker task is one full DAG node for the live cohort (scout pass, ingest pass, analyst pass), each bounded, verified, and reversible. Do not split one node into per-startup GoalBuddy tasks when the node is designed as one pass. Tiny tasks are only for isolated/high-risk failures.

## Board Health

PM owns board health. If the board looks stale or inconsistent, run the bundled checker:

```bash
node <skill-path>/scripts/check-goal-state.mjs docs/goals/idea-factory-e2e-live
```

## Canonical Board

Machine truth lives at `docs/goals/idea-factory-e2e-live/state.yaml`. If this charter and `state.yaml` disagree, `state.yaml` wins.

## Run Command

```text
/goal Follow docs/goals/idea-factory-e2e-live/goal.md.
```

## PM Loop

1. Read this charter and the execution contract.
2. Read `state.yaml`.
3. Check for a newer GoalBuddy version once, non-blocking.
4. Work only on the active task; dispatch idea-factory subagents for DAG nodes.
5. Parse receipts, run gates in code, route.
6. Write compact receipts; update the board; continue to the next safe slice.
7. Finish only with a Judge/PM audit mapping receipts back to the original outcome, recording `full_outcome_complete: true` only when live extraction + idea generation is genuinely done.
