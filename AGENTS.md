# idea-generator — project gotchas & commands

## Verify
```sh
python3 -m pytest tests/ -q        # 89 tests; load-bearing contract tests
python3 -c "from idea_factory.db import DB; DB('sid.db').init()"   # idempotent; safe on existing DB
```
- DB at `sid.db` — **Git LFS tracked** (see `.gitattributes`), NEVER `rm sid.db`; it's board truth. Use `DB('sid.db').init()` to add new tables — schema is `CREATE TABLE IF NOT EXISTS`, fully idempotent. After `git clone` on a fresh laptop, run `git lfs pull` to materialise `sid.db` + `scrapes/` (clone gives you LFS pointers otherwise); verify `file sid.db` says SQLite, not a 130-byte pointer.
- Receipt validation: `idea_factory.receipts.parse(raw)` returns a typed receipt or `ReceiptError`. It uses a balanced-brace `json.raw_decode` scan keyed off the `schema_version` marker — agents can quote walls of prose around the block. Stage-04 receipts disambiguate per-startup vs infra-node by the `infra_nodes_scored` field.
- Install skill to OpenCode after edits:
  ```sh
  cp -r skill ~/.config/opencode/skills/idea-factory
  cp agents/* ~/.config/opencode/agents/
  cp commands/idea-factory.md ~/.config/opencode/commands/
  ```

## DAG topology (the PM owns)
```
00 market-scout -> 01 ingestor -> 02 analyst -> 04 scorer -> 05 validator -> 06 builder
                                                   -> 07 clusterer (every 20 startups OR on demand)
```
- Entry contract non-negotiable: start from `pm.default_scout_input()`, never from a flat startup list.
- Gates live in code (`idea_factory/decisions.py`); agents cannot override them. Receipts are typed (`idea_factory/schema.py`).
- Honour rules: (1) validation before build (`builder_accepts`); (2) no-evidence wedges die (`evidence_gate`); (3) scorer never overwrites a human-locked `personal_fit` row; (4) clusterer uses the fixed Problem-Graph edge vocabulary (`classify_edge`) and the new Infrastructure-Graph vocabulary (`classify_infra_edge`).

## Meta-loop (the v2 conviction loop — highest-leverage output)
The **Infrastructure Graph** (added Aug 2026) converts the per-startup `infrastructure_ops` rows into a canonical `infrastructure_nodes` + `infrastructure_edges` graph and answers the v2 question: *"which infrastructure layer is sighted on ≥half of the analysed cohort?"*. Run it on demand (does NOT need the 20-startup clusterer threshold):
```sh
python3 -c "from idea_factory.db import DB; from idea_factory.pm import run_infra_convergence; import json; print(json.dumps(run_infra_convergence(DB('sid.db')), indent=2, default=str))"
```
Returns one row per `INTERNAL_PLATFORMS` slot; `convergence=True` rows are the candidate infrastructure plays. Echoed in the clusterer receipt's `summary`.

After the digest, score the convergent layers against the founder profile (scorer Mode B) and rank them:
```sh
python3 -c "from idea_factory.db import DB; from idea_factory.pm import run_infra_fit_digest; import json; print(json.dumps(run_infra_fit_digest(DB('sid.db'), 'skill/templates/founder-profile.md'), indent=2, default=str))"
```
`top_infra_node` is the single layer to bet on (fit × conviction × cross-cluster). Live board (Aug 07 2026): **Tracing/observability** is `top_infra_node`; 4 convergent nodes; cohort=82 analysed.

One-shot resume digest (counts + deterministic blockers for a fresh session):
```sh
python3 -c "from idea_factory.db import DB; from idea_factory.pm import board_status; import json; print(json.dumps(board_status(DB('sid.db')), indent=2, default=str))"
```

**Live snapshot (post ingest+analyse-51 + expand + www-dedup):** startups=**302** all scored | wedges=**6040** | primary=**302** | personal_fit=**302** | patterns=**36** | segments=**132** | CANONICAL=**30/30** | e2e=302/302 | convergent=5 | top_infra=Tracing/observability | next_action=**ingest** | wave #306–310 v0/Cloudflare Workers AI/Postman/Ramp/Rabbit — primaries Better UX / Faster / Better integrations / Vertical-specific / Mobile-first | pending **59** | tests=**90** green.

## Recursive fan-out (PRE-BUILD; depth-first; re-plan each fire)
```sh
python3 -c "from idea_factory.db import DB; from idea_factory.pm import plan_recursive_fanout; import json; print(json.dumps(plan_recursive_fanout(DB('sid.db')), indent=2, default=str))"
```
- **Priority:** `analyse → score_a → score_b → select → cluster → scout → ingest → idle`
- **Never** `builder` / stage 06 (`never_dispatch` on plan)
- Ingest **paused** while `ingested_awaiting_analyse ≥ 5` (was starving idea gen)
- Select: `pm.run_select_top_wedges(db)` — multi-winner shortlist (k=3, max 1 per type) + cohort primary type cap (~25%); `force=True` reselects all
- Ideas are **completed** at analyst (wedges) + select (shortlist), not at MVP

## Subagent dispatch contract
Dispatch via the Task tool with `subagent_type` of the agent name. The PM builds the typed `Input` from `idea_factory.pm` (`default_scout_input`, `build_scorer_input`, `build_infra_node_scorer_input`, `build_validator_input`, `build_builder_input`, `build_clusterer_input`). After dispatch, parse the returned JSON with `receipts.parse`; if `ReceiptError`, re-dispatch naming the gap. Run gates in code between dispatches — never trust prose for routing. The scorer has two modes: Mode A (per-startup → `personal_fit`) and Mode B (infra node → `infra_personal_fit`); stage-04 receipts disambiguate on `infra_nodes_scored`.

## Live-run gotchas (learned Aug 06)
- **YC /companies/<slug> pages routinely 404.** Ingestor's best-effort rule: log the 404 in `scrape_log`, fall back to the company's own homepage. Don't halt on a 404.
- **Context budget.** `webfetch` returns 60KB+ per startup page. The ingestor MUST compress with `pm.html_to_summary(html, max_chars=1200)` before reasoning, else a 5-startup cohort blows the prompt budget before SID extraction even starts.
- **SQLite datetime compare.** Schema stores `updated_at` in SQLite's space-format `datetime('now')` (e.g. `2026-08-06 14:33:23`). Boundary comparisons from Python must use `WHERE updated_at > datetime(?)` so SQLite normalises the `?`-bound isoformat T-format string; a bare lexicographic compare returns 0 for same-day updates.
- **Idempotent edges.** `INSERT OR IGNORE` returns `rowcount > 0` from the executed cursor (the just-executed statement), NOT `cur.total_changes` (cumulative since connection open). Use `res.rowcount`, not `cur.total_changes > 0` — otherwise duplicate inserts are reported as `True`.
- **Receipt bare-JSON.** Old `_BARE_RE` regex required `{"idea_factory_receipt_v1"` immediately after `{`, but real receipts are `{"schema_version":"idea_factory_receipt_v1"...}`. Don't bring the regex back; the `raw_decode` scan is correct.
- **`Pydantic extra="forbid"` + raw DB rows.** When you `cls(**dict(r))` from `SELECT *`, filter the row keys to `cls.model_fields` first — `updated_at` and other DB-only columns blow up `extra="forbid"` rows.
- **Subagent python scratch files.** Agents sometimes persist run scripts as `idea_factory/_*_run_*.py`. These must be `/tmp`-only, never committed. `.gitignore` has `_analyst_run_*.py` and `_*_run_*.py` glob patterns now.
- **Validator/builder are GATED on real-world side effects** (30 cold emails via gmail MCP; real MVP launches). They block on explicit user approval + (for the validator) gmail recipient pairing. Don't auto-resume — surface the exact blocker to the user.
- **Scorer blocks on empty `founder-profile.md`.** And on a human-locked `personal_fit` row (any `reviewed_at != NULL`). `db.upsert_personal_fit` returns `False` in that case and the scorer counts `rows_skipped_human_locked`.

## OpenCode skill Synagogue
`~/.config/opencode/skills/idea-factory/SKILL.md` is a copy, not a symlink. Mirror edits from `skill/SKILL.md` after every change or the running OpenCode session will use stale topology.