# idea-generator

An OpenCode skill + agent family that runs a continuous founder-led idea factory over YC startups. Ingests startups in markets where you have an unfair advantage, descends recursively into each one, generates ≥20 wedge ideas per startup, scores fit against your history, validates the top wedge with cold outreach BEFORE any MVP, then builds and launches the survivors and promotes cross-market patterns into a Pattern Library and Problem Graph.

## Install

```sh
# skill + subagents + slash command (idempotent; safe to re-run)
cp -r skill    ~/.config/opencode/skills/idea-factory
cp    agents/* ~/.config/opencode/agents/
cp    commands/idea-factory.md ~/.config/opencode/commands/

# init the DB (idempotent)
sqlite3 sid.db < skill/templates/schema.sql

# fill in your profile (the scorer blocks on an empty file)
$EDITOR skill/templates/founder-profile.md
```

Then in this session: `/idea-factory 5` to run a 5-startup cohort.

## What it does

- Ingests YC companies in a constrained 20-market pool (3 ICP clusters, not 20 independent dimensions).
- Runs a 10-level recursive descent per startup. L5 ("what changed recently") is the wedge generator; L7-L10 are a concentration funnel, not alternatives.
- Generates ≥20 wedges + N infrastructure-opportunity rows per startup. Rejects any wedge lacking a citation in the SID.
- Scores each wedge 0-10 across 8 axes from your filled-in founder profile. Human-locked rows are immutable to agents.
- Validates the top wedge with 30 cold sends via the gmail MCP. Reply rate is the single honesty metric. Only wedges with ≥3 pain-signal replies graduate.
- Builds an instrumented landing-page MVP only on graduated wedges. Uninstrumented MVPs are refused.
- Every ≥20 startups: cross-cluster pattern detection promotes to a Pattern Library and updates a Problem Graph with a fixed edge vocabulary.

## The agent family

| Agent | Stage | Write scope |
|---|---|---|
| ingestor  | 01 | `scrapes/`, `sid.db` |
| analyst   | 02-03 | `wedges`, `infrastructure_ops`, `recursive_path` |
| scorer    | 04 | `personal_fit`, `wedges.personal_fit_score` (human-locked rows read-only) |
| validator | 05 | `outreach_log`, gmail sends |
| builder   | 06 | `mvp/<wedge_id>/`, `waitlist`, gmail |
| clusterer | 07 | `pattern_library`, `problem_nodes`, `problem_edges` |

The PM (the skill itself) dispatches these via the Task tool and parses JSON receipts. Subagents do not pick the next stage; they return receipts.

## The loop

Continuous, no weekly cadence. Each cohort of N startups runs: ingest → descend+wedge → score (pause for human review) → validate → build (only graduates) → cluster (every ≥20 startups). Repeats until interrupted.

## Kill metric

After 8 weeks of runtime, ≥1 wedge must have 3+ prospect replies indicating real pain. If not reached, the loop halts. Do not iterate on outreach copy. Re-tune `founder-profile.md`, re-descend, re-wedge, then resume.

## Honour rules

1. Validation before build. Builder rejects wedges without an `outreach_log` receipt.
2. No-evidence wedges die. Analyst rejects any wedge lacking a `startup_competitive` or `startup_customer` citation.
3. Pattern promotion needs ≥3 sightings across ≥2 of the 3 ICP clusters. Within-cluster repeats are noise.
4. The scorer never overwrites a `personal_fit` row with non-NULL `reviewed_at`.
5. The Problem Graph uses the fixed edge vocabulary: `solves`, `sub-problem-of`, `suffers-from`, `enables`, `incumbent-of`, `OSS-alternative-to`. The clusterer rejects free-form edges.

## File map

```
skill/
  SKILL.md                       orchestrator contract
  references/workflows/0X-*.md   the 9 stage prompts the subagents read
  references/design/*.md         13 design notes (the why behind each call)
  templates/schema.sql           idempotent SQLite schema
  templates/founder-profile.md   human input the scorer reads
agents/idea-factory-*.md         6 subagent definitions
commands/idea-factory.md         /idea-factory slash command
raw/                             original broken-down design notes (history)
```

If a workflow feels under-specified, read its matching design note. The design note is the source of truth.

## Querying the OS (stage 08)

Natural-language queries unlock once the Problem Graph has a controlled vocabulary. Supported templates live in `skill/references/workflows/08-query-os.md`. The query layer resolves terms against the controlled vocab first and refuses free-text matching.