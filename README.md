# idea-generator

A founder-led idea factory, packaged as an OpenCode skill. **The skill IS the DAG.** Subagents ARE the nodes. Deterministic gates live in code (`idea_factory/decisions.py`); agent reasoning lives in prose prompts (`agents/*.md`). The PM orchestrates dispatch, validates typed receipts (`idea_factory/receipts.py`), runs gates in code, and routes.

> **This README is the session handoff.** If you are a fresh session on a fresh laptop: follow [Cold start on a new machine](#cold-start-on-a-new-machine) first, then read [Current board state (Aug 06 2026)](#current-board-state-aug-06-2026), then pick up from [Where the loop stands](#where-the-loop-stands).

---

## What it does (the v2 conviction loop)

Two parallel outputs:

1. **Per-startup wedges (the original v1 loop):** ingest a YC startup → recursive L1-L10 descent (L5 is the wedge generator) → 20+ evidence-cited wedges → 8-axis founder-fit scoring → top-wedge selection → 30 cold emails → graduation (≥5% reply + ≥3 pain-signal replies) → instrumented MVP. Cross-cluster patterns promote into a Pattern Library + Problem Graph.

2. **The meta-loop / Infrastructure Graph (v2 — the higher-leverage output):** every analyst pass also emits `infrastructure_ops` rows (which internal platforms each startup needs/builds). `pm.run_infra_convergence()` canonicalizes them into `infrastructure_nodes` (one per `internal_platform` slot) + `infrastructure_edges`, then flips `convergence=1` on any node sighted on **≥half the analysed cohort**. The scorer then projects the founder profile onto each convergent **layer** (Mode B, `infra_personal_fit`) instead of per-startup wedges, and `decisions.rank_infra_nodes_by_fit` returns the single layer to bet on (fit × conviction × cross-cluster).

The thesis: *don't ask "what startup should I build?" — ask "which infrastructure component appears across ≥20 startups?"* The convergence digest is the highest-leverage output and runs continuously, NOT gated behind the 20-startup clusterer threshold.

## The DAG (the PM owns this topology)

```
00 market-scout -> 01 ingestor -> 02 analyst -> 04 scorer -> 05 validator -> 06 builder
                                        \--> (meta-loop) pm.run_infra_convergence -> scorer Mode B -> rank_infra_nodes_by_fit
                                      07 clusterer (every 20 startups OR on demand)
```

**Entry contract is non-negotiable:** start from `pm.default_scout_input()`, dispatch the market scout, wait for its receipt, fan out on `candidates`. Never start from a flat startup list.

## Install (on THIS machine, already done — skip on a fresh clone)

```sh
git clone https://github.com/archit15singh/idea-generator
cd idea-generator
python3 -m pip install --break-system-packages -e ".[test]"   # pydantic + pytest
cp -r skill      ~/.config/opencode/skills/idea-factory
cp    agents/*   ~/.config/opencode/agents/
cp    commands/idea-factory.md ~/.config/opencode/commands/
```

Then `/idea-factory 5` runs a 5-startup cohort, or `/idea-factory <stage_marker>` resumes.

## Cold start on a new machine

**The DB + scrapes are tracked with Git LFS** so you can pull board truth on a fresh laptop. `sid.db` (board truth), `scrapes/` (raw fetches) are LFS-tracked via `.gitattributes`.

```sh
# 1. install git lfs (one-time)
brew install git-lfs && git lfs install

# 2. clone + checkout (LFS pointers resolve on checkout)
git clone https://github.com/archit15singh/idea-generator
cd idea-generator
git lfs pull    # force-download the LFS objects (sid.db, scrapes/) if the clone skipped them

# 3. python env + skill install
python3 -m pip install --break-system-packages -e ".[test]"
cp -r skill      ~/.config/opencode/skills/idea-factory
cp    agents/*   ~/.config/opencode/agents/
cp    commands/idea-factory.md ~/.config/opencode/commands/

# 4. verify
python3 -m pytest tests/ -q          # 89 passed
ls -la sid.db                        # should be ~500KB (real file, not an LFS pointer)
sqlite3 sid.db "SELECT COUNT(*) FROM startups;"   # 252
```

> **Gotcha:** after `git clone`, verify `sid.db` is a real SQLite file and NOT a 130-byte LFS pointer. `git lfs pull` fixes it. `file sid.db` should say "SQLite 3.x database".

## Verify (always)

```sh
python3 -m pytest tests/ -q        # 89 tests; load-bearing contract tests
python3 -c "from idea_factory.db import DB; DB('sid.db').init()"   # idempotent; safe on existing DB
```

## Meta-loop digest (run any time, the v2 output)

```sh
# convergence digest (which layers are sighted on >=half the cohort)
python3 -c "from idea_factory.db import DB; from idea_factory.pm import run_infra_convergence; import json; print(json.dumps(run_infra_convergence(DB('sid.db')), indent=2, default=str))"

# founder-fit scorecard (ranked layers + the single layer to bet on)
python3 -c "from idea_factory.db import DB; from idea_factory.pm import run_infra_fit_digest; import json; print(json.dumps(run_infra_fit_digest(DB('sid.db'), 'skill/templates/founder-profile.md'), indent=2, default=str))"
```

## Current board state (Aug 07 2026 — live `board_status`)

| Table | Count | Notes |
|-------|-------|-------|
| `startups` | 466 | **all scored** (analyse-84 Grafbase→Astronomer + cluster) |
| `analysed` (cohort) | 466 | CANONICAL **34/34** |
| `wedges` | 9320 | **466 primary** + shortlists |
| `infrastructure_ops` | ~2595+ | post analyse-80 |
| `infrastructure_nodes` | 10 | **5 convergent** |
| `infra_personal_fit` | 8 | Mode B; top_infra=Tracing/observability |
| `market_segments` | 140+ | CANONICAL **34** pool |
| `candidate_startups` | 475+ | pending **5** |
| `personal_fit` | 466 | all e2e |
| `pattern_library` | **174** | +Grafbase MCP, New Relic AI, Giskard red-team, Tavily web API, Astronomer |

**`plan_recursive_fanout` next_action = `ingest`**. Wave-40: Entro (#251 AI-native), Baseten (#252 Developer-first), Blink Ops (#253 **Better integrations**), Weaviate (#254 Better memory), Inngest (#255 Developer-first). Primary mix AI-native 59, Better evaluation 56, Better memory 54, Developer-first 46, Open source 13.

### The v2 ranked layers (live `run_infra_fit_digest` output)

| Layer | Sightings | Clusters | Founder-fit total | Rank score |
|-------|-----------|----------|-------------------|-----------|
| **Memory** | 7/8 | 3 | **72** | **0.9125 ← THE LAYER TO BET ON** |
| Tracing/observability | 6/8 | 3 | 68 | ~0.85 |
| Evaluation | 4/8 | 2 | 64 | ~0.79 |
| Retrieval/RAG | 5/8 | 2 | 60 | ~0.75 |
| Authentication | 5/8 | 3 | 55 | ~0.70 |
| Connectors | 7/8 | 3 | 50 | ~0.68 (shape outlier: market 8 but interest 5) |
| Prompt management | 4/8 | 1 | 46 | ~0.60 |
| Cost optimization | 7/8 | 3 | 42 | ~0.56 (shape outlier: market 8 but interest 3) |

**The conviction-loop winner is the Memory layer.** It's the only layer where every axis clears 8 on real shipped evidence (Memori = Rust+SQLite persistent memory, 43µs reads; PyCon India 2025 "Memory in AI Systems" talk; MemGPT fork). This matches the founder's documented unfair advantages in `skill/templates/founder-profile.md`.

**Shape outliers to review** (from the scorer's audit): Cost optimization + Connectors carry market-size 8 on 7/8 sightings but founder interest 3-5 — cohort-wide need, zero founder conviction; skip despite the sightings. Retrieval/RAG is a sharp-shape node (technical 9, knowledge 9 — pgvector home turf) but low moat — build it only fused with Memory, never standalone.

## Where the loop stands

- **Done (pushed):** CANONICAL **34/34**; e2e **466/466**; wedges **9320**; patterns **174**. Latest: **ingest+analyse-84** Grafbase/NewRelicAI/Giskard/Tavily/Astronomer + **cluster** (+5). Diversity Faster / Enterprise-first / Open source / AI-native / Developer-first. next **ingest**. **93 tests green.**
- **Next fire:** `ingest` next plan wave → analyse→score→select.
- **BLOCKED on human action (do NOT auto-resume):**
  - **Validator (05)** — cold emails via gmail MCP. Explicit user approval + recipient pairing.
  - **Builder (06)** — **disabled in pre-build** (`never_dispatch`). No stage 06.

## The next highest-ROI moves

1. **Ingest** next ≤5 candidates → analyse→score→select.
2. Expand CANONICAL markets past 30 if candidate pool thins.
3. Optional Mode B re-score after cohort growth.

## Subagent dispatch contract

Dispatch via the Task tool with `subagent_type` = the agent name. The PM builds the typed `Input` from `idea_factory.pm` builders: `default_scout_input`, `build_scorer_input`, `build_infra_node_scorer_input`, `build_validator_input`, `build_builder_input`, `build_clusterer_input`. After dispatch, run `idea_factory.receipts.parse(raw)`; if `ReceiptError`, re-dispatch naming the gap. Run gates in `decisions.py` between dispatches — never trust prose for routing.

The **scorer has two modes**: Mode A (`ScorerInput`: startup + wedges → `personal_fit`) and Mode B (`InfraNodeScorerInput`: infra node + backing startups → `infra_personal_fit`). The parser disambiguates stage-04 receipts by the `infra_nodes_scored` field.

## Kill metric (non-negotiable)

After 8 weeks of runtime, one wedge must have 3+ prospect replies indicating real pain. If `decisions.kill_metric_triggered(...)` returns `True`, STOP. Do not iterate outreach copy. Re-tune `founder-profile.md`, re-descend (02), re-wedge, then resume.

## Honour rules

1. Validation before build. `decisions.builder_accepts` enforces it at the builder door.
2. No-evidence wedges die. `decisions.evidence_gate` rejects them between 02 and 04.
3. Pattern promotion needs 3+ sightings across 2+ of the 3 ICP clusters (`promotion_gate`).
4. The scorer never overwrites a human-locked `personal_fit` OR `infra_personal_fit` row.
5. The Problem Graph uses the fixed edge vocabulary (`classify_edge`); the Infrastructure Graph uses `classify_infra_edge` (`needs`/`builds`/`uses`/`has-gap`).
6. The PM is the source of board truth. Subagents return receipts; gates route.

## Layout

```
idea_factory/           Python package: typed contracts + determinism
  schema.py             Pydantic types for every node Input + Receipt (incl. InfraNodeFitRow, InfraScorerReceipt)
  db.py                 typed SQLite layer (idempotent upserts; infra-graph + infra-fit methods)
  decisions.py          deterministic gates (evidence, graduation, convergence, rank_infra_nodes_by_fit, ...)
  receipts.py           parse + validate agent JSON receipts (balanced-brace raw_decode scan)
  pm.py                 PM-side builders + the meta-loop (run_infra_convergence, run_infra_fit_digest, CANONICAL_MARKETS)

skill/
  SKILL.md              the orchestrator (this IS the DAG topology; v2 meta-loop step baked in)
  references/workflows/  9 stage workflow prompts
  references/design/    13 design notes (the why)
  templates/schema.sql  idempotent SQLite schema (incl. infrastructure_nodes/edges, infra_personal_fit)
  templates/founder-profile.md  filled founder profile (the scorer reads this)

agents/idea-factory-*.md  7 subagent definitions (scout, ingestor, analyst, scorer, validator, builder, clusterer)
commands/idea-factory.md  /idea-factory slash command

sid.db                  board truth — Git LFS tracked, never `rm`
scrapes/                raw webfetch artifacts — Git LFS tracked
tests/test_80_20.py     73 load-bearing tests (schemas, gates, receipts, e2e, infra-graph, infra-fit)
AGENTS.md               project gotchas + commands (keep updated)
```

## Layout note for the OpenCode skill synagogue

`~/.config/opencode/skills/idea-factory/` is a **copy**, not a symlink. After editing `skill/SKILL.md`, `agents/*.md`, or `skill/templates/*`, mirror to the installed copies:

```sh
cp -r skill      ~/.config/opencode/skills/idea-factory
cp    agents/*   ~/.config/opencode/agents/
```

## Pushing data on a new laptop (git LFS)

```sh
git add sid.db scrapes/ .gitattributes .gitignore
git commit -m "Update board truth (sid.db + scrapes) via LFS"
git push
```

If LFS isn't installed on the new machine: `brew install git-lfs && git lfs install` BEFORE `git clone` (or run `git lfs pull` after).
