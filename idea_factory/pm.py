"""PM-side helpers for the idea-factory orchestrator.

This module exists because executing the DAG exposed real friction:
- webfetch returns 60KB+ of marketing noise per startup; the ingestor needs a
  summarisation step before extracting SID fields, not a wall of HTML
- building the typed Input for each node required inline-Python gluing several
  db queries; that belonged in one place, not in the orchestrator prompt
- the constrained "20-market pool" was prose in design notes; the PM had no
  programmatic seed list
- the kill-metric 8-week window had no persistent `started_at`

Everything here is deterministic; no agent reasoning. The agents stay prose.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

from idea_factory.schema import (
    BuilderInput,
    CandidateStartupRow,
    ClustererInput,
    InfraNodeFitRow,
    InfraNodeScorerInput,
    MarketScoutInput,
    MarketSegmentRow,
    OutreachLogRow,
    ScorerInput,
    StartupRow,
    ValidatorInput,
)

# --- canonical market pool (the DAG entry point) ---

# The DAG NEVER starts from a flat startup list. It starts from markets.
# The market scout recursively breaks each into sub-markets and candidates.
# 20 markets = design target (3 ICP clusters × verticals + orthogonal wedges).

CANONICAL_MARKETS = [
    # developer / founder ICP
    "AI Engineering",
    "Developer Tools",
    "Agent Infrastructure",
    "Technical Founder Tools",
    "Developer Infrastructure",
    # platform / infra ICP
    "Knowledge Management",
    "AI Infrastructure",
    "Observability",
    "Data Infrastructure",
    "MLOps and Evaluation",
    "Vector Search and Retrieval",
    "API and Integration Platforms",
    "Workflow Orchestration",
    # enterprise / security ICP
    "Cybersecurity",
    "Enterprise AI",
    "Enterprise Automation",
    "B2B Productivity",
    "Email Security",
    "Identity and Access",
    "Security Automation",
]

# Parallelism caps — recursive fan-out stays bounded so context/API budgets hold.
DEFAULT_SCOUT_MARKETS_PER_AGENT = 2
DEFAULT_INGEST_BATCH_SIZE = 5
DEFAULT_ANALYST_PARALLEL = 5
DEFAULT_SCORER_PARALLEL = 5
DEFAULT_VALIDATOR_PARALLEL = 3
DEFAULT_BUILDER_PARALLEL = 2
DEFAULT_MAX_FANOUT_WAVES = 8


def default_scout_input(depth: int = 2) -> MarketScoutInput:
    """The DAG's entry point. The PM hands this to the market scout."""
    return MarketScoutInput(markets=list(CANONICAL_MARKETS), depth=depth)


def _chunk(items: list, size: int) -> list[list]:
    """Split a list into fixed-size chunks (last chunk may be shorter)."""
    if size < 1:
        raise ValueError("chunk size must be >= 1")
    return [items[i : i + size] for i in range(0, len(items), size)]


# --- HTML-to-text helper: shrink webfetch footprint before reasoning ---

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_SCRIPT_STYLE_RE = re.compile(
    r"(?is)<(script|style|noscript)\b[^>]*>.*?</\1>",
)


def html_to_summary(html: str, max_chars: int = 1200) -> str:
    """Strip tags, collapse whitespace, truncate. For ingestor pre-processing.

    webfetch returns 60KB+ of marketing copy per startup. Without this, a
    5-startup cohort blows the context budget before SID extraction even
    starts. The ingestor reasons over the summary, not the raw page.

    Modern marketing sites ship huge inline <script>/<style> blocks; if we
    only strip tags those bodies become noise that crowds out real copy
    within max_chars. Drop script/style/noscript first.
    """
    cleaned = _SCRIPT_STYLE_RE.sub(" ", html)
    no_tags = _TAG_RE.sub(" ", cleaned)
    collapsed = _WS_RE.sub(" ", no_tags).strip()
    if len(collapsed) > max_chars:
        collapsed = collapsed[:max_chars] + " ...[truncated]"
    return collapsed


# --- recursive fan-out planning (PM dispatches waves in parallel) ---


def parent_markets_in_db(db) -> set[str]:
    """Distinct parent_market values already present in market_segments."""
    rows = db._conn.execute(
        "SELECT DISTINCT parent_market FROM market_segments WHERE parent_market IS NOT NULL"
    ).fetchall()
    return {r["parent_market"] for r in rows if r["parent_market"]}


def uncovered_markets(db, pool: Optional[list[str]] = None) -> list[str]:
    """Canonical markets with zero segments yet — scout these first."""
    pool = pool or list(CANONICAL_MARKETS)
    have = parent_markets_in_db(db)
    return [m for m in pool if m not in have]


def market_coverage(db, pool: Optional[list[str]] = None) -> dict:
    """How many of the canonical 20 markets have segments + analysed startups."""
    pool = pool or list(CANONICAL_MARKETS)
    have_segments = parent_markets_in_db(db)
    # parent markets that already produced at least one analysed startup
    rows = db._conn.execute(
        """
        SELECT DISTINCT ms.parent_market AS pm
        FROM startups s
        JOIN candidate_startups cs ON cs.website = s.website
        JOIN market_segments ms ON ms.id = cs.market_segment_id
        WHERE s.stage_marker IN
          ('analysed','scored','validated','graduated','built')
          AND ms.parent_market IS NOT NULL
        """
    ).fetchall()
    have_analysed = {r["pm"] for r in rows if r["pm"]}
    covered_segments = [m for m in pool if m in have_segments]
    covered_analysed = [m for m in pool if m in have_analysed]
    return {
        "pool_size": len(pool),
        "with_segments": len(covered_segments),
        "with_analysed_startups": len(covered_analysed),
        "uncovered_markets": [m for m in pool if m not in have_segments],
        "markets_without_analysed": [m for m in pool if m not in have_analysed],
        "covered_markets": covered_segments,
    }


def scout_fanout_inputs(
    db,
    *,
    markets_per_agent: int = DEFAULT_SCOUT_MARKETS_PER_AGENT,
    depth: int = 2,
    only_uncovered: bool = True,
    pool: Optional[list[str]] = None,
) -> list[MarketScoutInput]:
    """Recursive market fan-out: one typed Input per parallel scout agent.

    Prefer uncovered markets. If all 20 already have segments and
    only_uncovered=True, returns [] (re-scout full pool via default_scout_input
    when the PM wants a refresh).
    """
    pool = pool or list(CANONICAL_MARKETS)
    markets = uncovered_markets(db, pool) if only_uncovered else list(pool)
    if not markets:
        return []
    return [
        MarketScoutInput(markets=chunk, depth=depth)
        for chunk in _chunk(markets, markets_per_agent)
    ]


def _pending_with_parent_market(db) -> list[tuple[CandidateStartupRow, Optional[str]]]:
    """Pending candidates joined to their parent_market for diversity fan-out."""
    pending = db.candidates_for_ingest()
    if not pending:
        return []
    # website -> parent_market
    rows = db._conn.execute(
        """
        SELECT cs.website, ms.parent_market
        FROM candidate_startups cs
        LEFT JOIN market_segments ms ON ms.id = cs.market_segment_id
        """
    ).fetchall()
    parent_by_site = {r["website"]: r["parent_market"] for r in rows}
    return [(c, parent_by_site.get(c.website)) for c in pending]


def diversify_candidates_round_robin(
    pending: list[tuple[CandidateStartupRow, Optional[str]]],
    limit: int,
    prefer_markets: Optional[list[str]] = None,
) -> list[CandidateStartupRow]:
    """Pick up to `limit` candidates, round-robin across parent markets.

    Markets listed in prefer_markets (e.g. those with no analysed startups)
    are drained first. This is the recursive segment→candidate fan-out that
    stops the cohort from collapsing into one over-scouted market.
    """
    if limit < 1 or not pending:
        return []
    # group by parent
    by_market: dict[str, list[CandidateStartupRow]] = {}
    for cand, parent in pending:
        key = parent or "_unknown"
        by_market.setdefault(key, []).append(cand)

    order: list[str] = []
    prefer = prefer_markets or []
    for m in prefer:
        if m in by_market and m not in order:
            order.append(m)
    for m in sorted(by_market.keys()):
        if m not in order:
            order.append(m)

    picked: list[CandidateStartupRow] = []
    # round-robin until limit or all empty
    while len(picked) < limit:
        progress = False
        for m in order:
            bucket = by_market.get(m) or []
            if not bucket:
                continue
            picked.append(bucket.pop(0))
            progress = True
            if len(picked) >= limit:
                break
        if not progress:
            break
    return picked


def ingest_fanout_batches(
    db,
    *,
    batch_size: int = DEFAULT_INGEST_BATCH_SIZE,
    max_batches: int = DEFAULT_MAX_FANOUT_WAVES,
    diversify: bool = True,
) -> list[list[CandidateStartupRow]]:
    """Recursive candidate fan-out: parallel ingest waves.

    Each inner list is one parallel wave (dispatch one ingestor per candidate
    inside the wave, or one agent per wave — PM's choice). Waves themselves
    are sequential across fires if needed.
    """
    pending = _pending_with_parent_market(db)
    if not pending:
        return []
    cov = market_coverage(db)
    prefer = cov["markets_without_analysed"]
    if diversify:
        ordered = diversify_candidates_round_robin(
            pending, limit=len(pending), prefer_markets=prefer,
        )
    else:
        ordered = [c for c, _ in pending]
    # cap total work this plan emits
    cap = batch_size * max_batches
    ordered = ordered[:cap]
    return _chunk(ordered, batch_size)


def startups_at_stage(db, marker: str) -> list[int]:
    """Startup ids with the given stage_marker, ordered by id."""
    rows = db._conn.execute(
        "SELECT id FROM startups WHERE stage_marker = ? ORDER BY id",
        (marker,),
    ).fetchall()
    return [int(r["id"]) for r in rows]


def analyst_fanout_ids(
    db, *, parallel: int = DEFAULT_ANALYST_PARALLEL, max_waves: int = DEFAULT_MAX_FANOUT_WAVES,
) -> list[list[int]]:
    """Startups at 'ingested' ready for recursive L1-L10 analyst, in waves."""
    ids = startups_at_stage(db, "ingested")
    return _chunk(ids[: parallel * max_waves], parallel)


# Cap: never open more ingest while this many sit at stage_marker='ingested'.
# Prevents the loop from drowning the board in SID rows with zero wedges.
MAX_INGESTED_AWAITING_ANALYSE = 5

# This factory is PRE-BUILD ONLY. Stage 06 (builder) is never planned or dispatched.
PREBUILD_TERMINAL_STAGES = frozenset({
    "analyse", "score_a", "score_b", "select", "cluster", "scout", "ingest", "idle",
})


def scorer_mode_a_fanout_ids(
    db, *, parallel: int = DEFAULT_SCORER_PARALLEL, max_waves: int = DEFAULT_MAX_FANOUT_WAVES,
) -> list[list[int]]:
    """Analysed startups that still need Mode A scoring.

    Includes: no personal_fit row, OR any evidence wedge missing personal_fit_score
    (so top_wedge ranking is not an insertion-order lottery).
    Skips startups whose personal_fit is human-locked (reviewed_at set) AND all
    wedges already scored — those need an explicit unlock, not a silent rescore.
    """
    rows = db._conn.execute(
        """
        SELECT DISTINCT s.id FROM startups s
        LEFT JOIN personal_fit pf ON pf.startup_id = s.id
        LEFT JOIN wedges w ON w.startup_id = s.id
          AND w.evidence IS NOT NULL AND TRIM(w.evidence) != ''
        WHERE s.stage_marker IN ('analysed', 'scored')
          AND (
            pf.startup_id IS NULL
            OR (
              (pf.reviewed_at IS NULL)
              AND EXISTS (
                SELECT 1 FROM wedges w2
                WHERE w2.startup_id = s.id
                  AND w2.evidence IS NOT NULL AND TRIM(w2.evidence) != ''
                  AND w2.personal_fit_score IS NULL
              )
            )
          )
        ORDER BY s.id
        """
    ).fetchall()
    ids = [int(r["id"]) for r in rows]
    return _chunk(ids[: parallel * max_waves], parallel)


def scorer_mode_b_fanout_ids(
    db, *, parallel: int = DEFAULT_SCORER_PARALLEL,
) -> list[list[int]]:
    """Convergent infra nodes with no infra_personal_fit yet — parallel Mode B."""
    rows = db._conn.execute(
        """
        SELECT n.id FROM infrastructure_nodes n
        LEFT JOIN infra_personal_fit f ON f.infra_node_id = n.id
        WHERE n.convergence = 1 AND n.retired_at IS NULL AND f.infra_node_id IS NULL
        ORDER BY n.sightings DESC, n.id
        """
    ).fetchall()
    ids = [int(r["id"]) for r in rows]
    return _chunk(ids, parallel) if ids else []


def select_wedge_fanout_ids(db, *, force: bool = False) -> list[int]:
    """Fitted startups that need selection (or all of them when force=True).

    Pre-build terminal step: run_select_top_wedges. Never implies builder.
    force=True re-runs selection over every fitted startup (diversity reselect).
    """
    sql = """
        SELECT s.id FROM startups s
        JOIN personal_fit pf ON pf.startup_id = s.id
        WHERE s.stage_marker IN ('analysed', 'scored')
          AND EXISTS (
            SELECT 1 FROM wedges w
            WHERE w.startup_id = s.id
              AND w.evidence IS NOT NULL AND TRIM(w.evidence) != ''
          )
    """
    if not force:
        sql += """
          AND NOT EXISTS (
            SELECT 1 FROM wedges w2
            WHERE w2.startup_id = s.id AND w2.selected = 1
          )
        """
    sql += " ORDER BY s.id"
    rows = db._conn.execute(sql).fetchall()
    return [int(r["id"]) for r in rows]


def run_select_top_wedges(
    db,
    *,
    force: bool = False,
    shortlist_k: int = 3,
    max_per_type: int = 1,
    global_primary_cap_fraction: float = 0.25,
) -> list[dict]:
    """Deterministic pre-build selection with diversity + multi-winner shortlist.

    Per startup:
      - primary wedge under a cohort-wide type cap (≤25% of startups share a
        primary type by default) so selection does not collapse to one mode
        (the Better-memory failure)
      - shortlist of up to `shortlist_k` distinct wedge_types, all marked
        selected=1 (multi-winner shortlist for pre-build review)

    force=True clears prior selections and re-runs over all fitted startups.
    Pure code — no agent, no builder.
    """
    from idea_factory.decisions import (
        assign_primary_with_global_cap,
        shortlist_wedges,
    )

    sids = select_wedge_fanout_ids(db, force=force)
    candidates: list[tuple[int, list, object]] = []
    for sid in sids:
        wedges = db.get_wedges(sid)
        fit = db.get_personal_fit(sid)
        if fit is None or not wedges:
            continue
        candidates.append((sid, wedges, fit))

    primaries = assign_primary_with_global_cap(
        candidates, cap_fraction=global_primary_cap_fraction,
    )

    results: list[dict] = []
    for sid, wedges, fit in candidates:
        # clear prior selections when force or any prior select
        for w in wedges:
            if w.selected and w.id is not None:
                db.mark_wedge_selected(w.id, False)

        primary = primaries.get(sid)
        if primary is None:
            results.append({
                "startup_id": sid, "selected": None, "shortlist": [],
                "reason": "no evidence wedge",
            })
            continue

        # shortlist: primary first, then other types by rank (max_per_type)
        blocked_for_rest = set()  # don't block — shortlist_wedges uses max_per_type
        raw_sl = shortlist_wedges(
            wedges, fit, k=shortlist_k, max_per_type=max_per_type,
        )
        # ensure primary is first even if global cap reordered it vs pure rank
        shortlist: list = []
        seen_ids: set[int] = set()
        if primary.id is not None:
            shortlist.append(primary)
            seen_ids.add(primary.id)
        for w, _score in raw_sl:
            if w.id is None or w.id in seen_ids:
                continue
            shortlist.append(w)
            seen_ids.add(w.id)
            if len(shortlist) >= shortlist_k:
                break

        for w in shortlist:
            if w.id is not None:
                db.mark_wedge_selected(w.id, True)

        if db.get_startup(sid) and db.get_startup(sid).stage_marker == "analysed":
            db.set_stage_marker(sid, "scored")

        results.append({
            "startup_id": sid,
            "selected": primary.id,
            "wedge_type": primary.wedge_type,
            "personal_fit_score": primary.personal_fit_score,
            "shortlist": [
                {
                    "id": w.id,
                    "wedge_type": w.wedge_type,
                    "personal_fit_score": w.personal_fit_score,
                    "primary": w.id == primary.id,
                }
                for w in shortlist
            ],
            "shortlist_types": [w.wedge_type for w in shortlist],
        })
    return results


def plan_recursive_fanout(
    db,
    *,
    scout_markets_per_agent: int = DEFAULT_SCOUT_MARKETS_PER_AGENT,
    ingest_batch_size: int = DEFAULT_INGEST_BATCH_SIZE,
    analyst_parallel: int = DEFAULT_ANALYST_PARALLEL,
    scorer_parallel: int = DEFAULT_SCORER_PARALLEL,
    depth: int = 2,
    max_ingested_backlog: int = MAX_INGESTED_AWAITING_ANALYSE,
) -> dict:
    """Single source of truth for the PM's parallel dispatch wave (PRE-BUILD ONLY).

    Priority is depth-first through pre-build stages so the board never piles
    up ingested SIDs with zero wedges (the failure mode of ingest-first loops):

      1. analyse  — drain stage_marker='ingested' (ideas get generated HERE)
      2. score_a  — personal_fit + per-wedge scores
      3. score_b  — convergent infra founder-fit (v2)
      4. select   — top_wedge mark (deterministic; terminal pre-build artifact)
      5. cluster  — pattern library when threshold met
      6. scout    — only uncovered canonical markets
      7. ingest   — ONLY if ingested-awaiting-analyse < max_ingested_backlog
      8. idle     — convergence digest + prebuild summary

    NEVER returns builder / stage 06. Validation (05) is human-gated and not
    auto-planned here — surface it in blockers when top wedges are selected.
    """
    cov = market_coverage(db)
    scout_inputs = scout_fanout_inputs(
        db, markets_per_agent=scout_markets_per_agent, depth=depth, only_uncovered=True,
    )
    ingest_batches = ingest_fanout_batches(db, batch_size=ingest_batch_size)
    analyse_waves = analyst_fanout_ids(db, parallel=analyst_parallel)
    score_a_waves = scorer_mode_a_fanout_ids(db, parallel=scorer_parallel)
    score_b_waves = scorer_mode_b_fanout_ids(db, parallel=scorer_parallel)
    select_ids = select_wedge_fanout_ids(db)
    ingested_backlog = len(startups_at_stage(db, "ingested"))
    clusterer_inp = build_clusterer_input(db)
    new_since = db.count_startups_since(clusterer_inp.last_run_at)
    cluster_ready = new_since >= clusterer_inp.min_new_since_last

    # Depth-first pre-build — analyse before any more ingest.
    if analyse_waves:
        next_action = "analyse"
        wave = {
            "stage": "02",
            "agent": "idea-factory-analyst",
            "parallel": len(analyse_waves[0]),
            "startup_ids": analyse_waves[0],
            "remaining_waves": len(analyse_waves) - 1,
            "ingested_backlog": ingested_backlog,
        }
    elif score_a_waves:
        next_action = "score_a"
        wave = {
            "stage": "04",
            "agent": "idea-factory-scorer",
            "mode": "A",
            "parallel": len(score_a_waves[0]),
            "startup_ids": score_a_waves[0],
            "remaining_waves": len(score_a_waves) - 1,
        }
    elif score_b_waves:
        next_action = "score_b"
        wave = {
            "stage": "04",
            "agent": "idea-factory-scorer",
            "mode": "B",
            "parallel": len(score_b_waves[0]),
            "infra_node_ids": score_b_waves[0],
            "remaining_waves": len(score_b_waves) - 1,
        }
    elif select_ids:
        next_action = "select"
        wave = {
            "stage": "04b",
            "agent": None,  # deterministic: pm.run_select_top_wedges
            "parallel": 0,
            "startup_ids": select_ids[:scorer_parallel],
            "hint": "run_select_top_wedges(db) — shortlist k=3 + global type cap; no builder",
        }
    elif cluster_ready:
        next_action = "cluster"
        wave = {
            "stage": "07",
            "agent": "idea-factory-clusterer",
            "parallel": 1,
            "min_new_since_last": clusterer_inp.min_new_since_last,
            "new_since": new_since,
        }
    elif scout_inputs:
        next_action = "scout"
        wave = {
            "stage": "00",
            "agent": "idea-factory-market-scout",
            "parallel": len(scout_inputs),
            "inputs": [
                {"markets": inp.markets, "depth": inp.depth} for inp in scout_inputs
            ],
        }
    elif ingest_batches and ingested_backlog < max_ingested_backlog:
        next_action = "ingest"
        first = ingest_batches[0]
        wave = {
            "stage": "01",
            "agent": "idea-factory-ingestor",
            "parallel": len(first),
            "candidates": [
                {"name": c.name, "website": c.website, "market_segment_id": c.market_segment_id}
                for c in first
            ],
            "remaining_batches": len(ingest_batches) - 1,
            "ingested_backlog": ingested_backlog,
            "max_ingested_backlog": max_ingested_backlog,
        }
    else:
        next_action = "idle"
        blocked_ingest = bool(ingest_batches) and ingested_backlog >= max_ingested_backlog
        wave = {
            "stage": None,
            "agent": None,
            "parallel": 0,
            "hint": (
                "run_infra_convergence + run_infra_fit_digest + board_status; "
                "NEVER dispatch builder (06)"
            ),
            "ingest_paused_for_analyse_backlog": blocked_ingest,
            "ingested_backlog": ingested_backlog,
        }

    return {
        "next_action": next_action,
        "wave": wave,
        "coverage": cov,
        "prebuild_only": True,
        "never_dispatch": ["06", "idea-factory-builder"],
        "queues": {
            "scout_agents": len(scout_inputs),
            "ingest_batches": len(ingest_batches) if ingested_backlog < max_ingested_backlog else 0,
            "pending_ingest": sum(len(b) for b in ingest_batches),
            "ingested_awaiting_analyse": ingested_backlog,
            "analyse_waves": len(analyse_waves),
            "score_a_waves": len(score_a_waves),
            "score_b_waves": len(score_b_waves),
            "select_pending": len(select_ids),
            "cluster_ready": cluster_ready,
        },
    }


# --- typed Input builders: PM uses these to construct dispatch payloads ---

# These wrap the db queries so the orchestrator prompt doesn't have inline
# Python gluing several calls. Inputs are typed; the PM validates them before
# handing to a subagent.


def build_analyst_input(db, startup_id: int):
    """ Delegate to db.get_sid_for_analyst — already exists. """
    return db.get_sid_for_analyst(startup_id)


def build_scorer_input(
    db,
    startup_id: int,
    founder_profile_path: str,
) -> ScorerInput:
    wedges = db.get_wedges(startup_id)
    if not wedges:
        raise ValueError(f"startup {startup_id} has no wedges; run analyst first")
    existing = db.get_personal_fit(startup_id)
    return ScorerInput(
        startup_id=startup_id,
        wedges=wedges,
        founder_profile_path=founder_profile_path,
        existing_fit=existing,
    )


def build_infra_node_scorer_input(
    db,
    infra_node_id: int,
    founder_profile_path: str,
) -> InfraNodeScorerInput:
    """Build the scorer's meta-loop (v2) input for one convergent infra node.

    The scorer projects the founder profile onto the LAYER: the node's
    canonical_name + mini_spec + the startups that sighted the need give it
    the context to judge 8-axis fit. Only convergent nodes should reach here
    (the PM filters to `convergence=1` first); this builder is per-node, so
    the PM dispatches the scorer once per convergent layer.
    """
    node_by_id = dict(db.infrastructure_nodes())
    node = node_by_id.get(infra_node_id)
    if node is None:
        raise ValueError(f"infra node {infra_node_id} not found; run clusterer first")
    backing = db.startups_backing_infra_node(infra_node_id)
    existing = db.get_infra_personal_fit(infra_node_id)
    return InfraNodeScorerInput(
        infra_node_id=infra_node_id,
        node=node,
        backing_startups=backing,
        founder_profile_path=founder_profile_path,
        existing_fit=existing,
    )


def run_infra_fit_digest(db, founder_profile_path: str, fraction: float = 0.5):
    """The PM-facing meta-loop scorecard: for every convergent infra node,
    emit the canonical name, its founder-fit score (if scored), the sightings
    and clusters that drove convergence, and — if enough nodes are scored —
    the single 'bet on this layer' winner from decisions.top_infra_node.

    This is the v2 conviction loop: it turns the Infrastructure Graph into a
    ranked, founder-fit-weighted list of the layers to actually build, instead
    of a flat list of per-startup wedges.

    `founder_profile_path` is accepted for API symmetry with the scorer builders
    (callers already pass it); this digest is read-only over already-scored rows.
    """
    from idea_factory.decisions import rank_infra_nodes_by_fit, top_infra_node

    _ = founder_profile_path  # reserved for future re-score hooks; keep call sites stable
    _ = fraction

    conv = db.convergent_infra_nodes()
    scored: list[tuple[int, str, InfraNodeFitRow]] = []
    sightings: dict[int, int] = {}
    clusters: dict[int, int] = {}
    fit_by_id: dict[int, InfraNodeFitRow] = {}
    clusters_list: dict[int, list[str]] = {}
    for node_id, node in conv:
        sightings[node_id] = node.sightings
        clusters[node_id] = len(node.clusters_seen)
        clusters_list[node_id] = list(node.clusters_seen)
        fit = db.get_infra_personal_fit(node_id)
        if fit is not None:
            scored.append((node_id, node.canonical_name, fit))
            fit_by_id[node_id] = fit

    cohort = db.count_analysed_startups()
    ranked = rank_infra_nodes_by_fit(scored, sightings, clusters, cohort)
    winner = top_infra_node(scored, sightings, clusters, cohort)
    ranked_rows = []
    for (nid, name), s in ranked:
        fit = fit_by_id[nid]
        ranked_rows.append({
            "infra_node_id": nid,
            "canonical_name": name,
            "score": s,
            "fit_total": fit.total,
            "sightings": sightings.get(nid, 0),
            "clusters": clusters_list.get(nid, []),
            "interest": fit.interest,
            "technical_advantage": fit.technical_advantage,
        })
    return {
        "cohort": cohort,
        "convergent_nodes": len(conv),
        "scored_nodes": len(scored),
        "ranked": ranked_rows,
        "top_infra_node": {
            "infra_node_id": winner[0],
            "canonical_name": winner[1],
            "score": ranked_rows[0]["score"] if ranked_rows else None,
            "fit_total": ranked_rows[0]["fit_total"] if ranked_rows else None,
            "sightings": ranked_rows[0]["sightings"] if ranked_rows else None,
        }
        if winner else None,
    }


def board_status(db) -> dict:
    """One-shot PM digest over board truth. Pure reads; no agent reasoning.

    Surfaces the counts that matter for routing decisions (cohort size vs
    clusterer threshold, locked personal_fit rows, infra winner) so a fresh
    session can resume without inventing SQL.
    """
    from idea_factory.decisions import top_infra_node

    def _count(sql: str, params: tuple = ()) -> int:
        return int(db._conn.execute(sql, params).fetchone()[0])

    startups = _count("SELECT COUNT(*) FROM startups")
    analysed = db.count_analysed_startups()
    wedges = _count("SELECT COUNT(*) FROM wedges")
    wedges_with_evidence = _count(
        "SELECT COUNT(*) FROM wedges WHERE evidence IS NOT NULL AND TRIM(evidence) != ''"
    )
    candidates = _count("SELECT COUNT(*) FROM candidate_startups")
    pending_ingest = len(db.candidates_for_ingest())
    segments = _count("SELECT COUNT(*) FROM market_segments")
    infra_ops = _count("SELECT COUNT(*) FROM infrastructure_ops")
    infra_nodes = _count("SELECT COUNT(*) FROM infrastructure_nodes")
    convergent = _count(
        "SELECT COUNT(*) FROM infrastructure_nodes WHERE convergence = 1 AND retired_at IS NULL"
    )
    personal_fit = _count("SELECT COUNT(*) FROM personal_fit")
    personal_fit_locked = _count(
        "SELECT COUNT(*) FROM personal_fit WHERE reviewed_at IS NOT NULL"
    )
    infra_fit = _count("SELECT COUNT(*) FROM infra_personal_fit")
    infra_fit_locked = _count(
        "SELECT COUNT(*) FROM infra_personal_fit WHERE reviewed_at IS NOT NULL"
    )
    patterns = _count(
        "SELECT COUNT(*) FROM pattern_library WHERE retired_at IS NULL"
    )
    outreach = _count("SELECT COUNT(*) FROM outreach_log")

    # Stage histogram
    stage_rows = db._conn.execute(
        "SELECT COALESCE(stage_marker, 'unset') AS m, COUNT(*) AS n "
        "FROM startups GROUP BY m ORDER BY n DESC"
    ).fetchall()
    by_stage = {r["m"]: r["n"] for r in stage_rows}

    # Infra winner if scored
    scored: list[tuple[int, str, InfraNodeFitRow]] = []
    sightings: dict[int, int] = {}
    clusters: dict[int, int] = {}
    for node_id, node in db.convergent_infra_nodes():
        sightings[node_id] = node.sightings
        clusters[node_id] = len(node.clusters_seen)
        fit = db.get_infra_personal_fit(node_id)
        if fit is not None:
            scored.append((node_id, node.canonical_name, fit))
    winner = top_infra_node(scored, sightings, clusters, analysed)

    started_at = get_runtime_started_at(db)
    clusterer_inp = build_clusterer_input(db)
    new_since = db.count_startups_since(clusterer_inp.last_run_at)
    coverage = market_coverage(db)
    fanout = plan_recursive_fanout(db)

    return {
        "startups": startups,
        "analysed": analysed,
        "by_stage": by_stage,
        "wedges": wedges,
        "wedges_with_evidence": wedges_with_evidence,
        "candidates": candidates,
        "pending_ingest": pending_ingest,
        "market_segments": segments,
        "infrastructure_ops": infra_ops,
        "infrastructure_nodes": infra_nodes,
        "convergent_nodes": convergent,
        "personal_fit": personal_fit,
        "personal_fit_locked": personal_fit_locked,
        "infra_personal_fit": infra_fit,
        "infra_personal_fit_locked": infra_fit_locked,
        "pattern_library": patterns,
        "outreach_sends": outreach,
        "runtime_started_at": started_at.isoformat() if started_at else None,
        "market_coverage": coverage,
        "fanout": {
            "next_action": fanout["next_action"],
            "wave": fanout["wave"],
            "queues": fanout["queues"],
        },
        "clusterer": {
            "last_run_at": (
                clusterer_inp.last_run_at.isoformat()
                if clusterer_inp.last_run_at else None
            ),
            "new_startups_since_last": new_since,
            "min_new_required": clusterer_inp.min_new_since_last,
            "ready": new_since >= clusterer_inp.min_new_since_last,
        },
        "top_infra_node": (
            {"infra_node_id": winner[0], "canonical_name": winner[1]}
            if winner else None
        ),
        "blockers": _board_blockers(
            analysed=analysed,
            personal_fit=personal_fit,
            personal_fit_locked=personal_fit_locked,
            infra_fit=infra_fit,
            convergent=convergent,
            outreach=outreach,
            patterns=patterns,
            new_since=new_since,
            min_clusterer=clusterer_inp.min_new_since_last,
            pending_ingest=pending_ingest,
            startups=startups,
            uncovered_markets=len(coverage["uncovered_markets"]),
            pool_size=coverage["pool_size"],
            ingested_backlog=fanout["queues"].get("ingested_awaiting_analyse", 0),
            select_pending=fanout["queues"].get("select_pending", 0),
        ),
        "prebuild_only": True,
        "never_dispatch": fanout.get("never_dispatch", ["06", "idea-factory-builder"]),
    }


def _board_blockers(
    *,
    analysed: int,
    personal_fit: int,
    personal_fit_locked: int,
    infra_fit: int,
    convergent: int,
    outreach: int,
    patterns: int,
    new_since: int,
    min_clusterer: int,
    pending_ingest: int,
    startups: int,
    uncovered_markets: int = 0,
    pool_size: int = 20,
    ingested_backlog: int = 0,
    select_pending: int = 0,
) -> list[str]:
    """Deterministic resume hints for a fresh PM session (pre-build only)."""
    blockers: list[str] = []
    if startups == 0:
        blockers.append("empty board: run market-scout then ingestor (or git lfs pull sid.db)")
        return blockers
    if ingested_backlog > 0:
        blockers.append(
            f"PRE-BUILD PRIORITY: {ingested_backlog} startups ingested await analyst "
            "(ideas not generated yet) — plan next_action=analyse; do not ingest more"
        )
    if uncovered_markets > 0:
        blockers.append(
            f"scout fan-out: {uncovered_markets}/{pool_size} canonical markets still "
            "have zero segments — plan_recursive_fanout → scout"
        )
    if pending_ingest > 0 and analysed < 20 and ingested_backlog == 0:
        blockers.append(
            f"candidates remain: {pending_ingest} pending ingest "
            f"({analysed} analysed) — after analyse queue is clear"
        )
    if personal_fit_locked > 0 and personal_fit == personal_fit_locked:
        blockers.append(
            f"scorer Mode A: {personal_fit_locked} personal_fit rows human-locked "
            "(unlock reviewed_at=NULL or force=True to re-score)"
        )
    if convergent > 0 and infra_fit < convergent:
        blockers.append(
            f"scorer Mode B incomplete: {infra_fit}/{convergent} convergent layers scored"
        )
    if select_pending > 0:
        blockers.append(
            f"select pending: {select_pending} fitted startups need run_select_top_wedges"
        )
    if personal_fit > 0 and outreach == 0:
        blockers.append(
            "validator optional/human-gated (pre-build); no outreach yet — not a builder cue"
        )
    if new_since < min_clusterer and patterns == 0:
        blockers.append(
            f"clusterer waiting: {new_since}/{min_clusterer} new startups "
            "(or min_new_since_last=0 for on-demand pass)"
        )
    blockers.append("builder disabled: skill is pre-build only (never dispatch stage 06)")
    return blockers


def build_validator_input(
    db,
    startup_id: int,
    wedge_id: int,
    prospect_persona_hint: Optional[str] = None,
) -> ValidatorInput:
    wedges = db.get_wedges(startup_id)
    wedge = next((w for w in wedges if w.id == wedge_id), None)
    if wedge is None:
        raise ValueError(f"wedge {wedge_id} not found on startup {startup_id}")
    fit = db.get_personal_fit(startup_id)
    if fit is None:
        raise ValueError(f"no personal_fit for startup {startup_id}; run scorer first")
    return ValidatorInput(
        startup_id=startup_id,
        wedge=wedge,
        personal_fit=fit,
        prospect_persona_hint=prospect_persona_hint,
    )


def build_builder_input(db, startup_id: int, wedge_id: int) -> BuilderInput:
    wedges = db.get_wedges(startup_id)
    wedge = next((w for w in wedges if w.id == wedge_id), None)
    if wedge is None:
        raise ValueError(f"wedge {wedge_id} not found on startup {startup_id}")
    outreach = db.outreach_for_wedge(wedge_id)
    pain = [r for r in outreach if r.reply_pain_signal]
    sid = db.get_startup(startup_id)
    if sid is None:
        raise ValueError(f"startup {startup_id} not found")
    return BuilderInput(
        startup_id=startup_id,
        wedge=wedge,
        pain_replies=pain,
        sid=sid,
    )


def build_clusterer_input(db, min_new_since_last: int = 20) -> ClustererInput:
    last_run = db._conn.execute(
        "SELECT value AS last FROM runtime_meta WHERE key = 'last_clusterer_run'"
    ).fetchone()
    last_at = None
    if last_run and last_run["last"]:
        try:
            last_at = datetime.fromisoformat(last_run["last"].replace("Z", "+00:00"))
        except ValueError:
            last_at = None
    return ClustererInput(
        min_new_since_last=min_new_since_last,
        last_run_at=last_at,
    )


# --- kill-metric window persistence ---


def mark_runtime_started(db) -> None:
    """Stamp the kill-metric window start. Idempotent on first call only."""
    db._conn.execute(
        """
        INSERT INTO runtime_meta (key, value) VALUES ('started_at', ?)
        ON CONFLICT(key) DO UPDATE SET value = value
        WHERE key = 'started_at' AND value IS NULL
        """,
        (datetime.now(timezone.utc).isoformat(timespec="seconds"),),
    )
    db._conn.commit()


def get_runtime_started_at(db) -> Optional[datetime]:
    r = db._conn.execute(
        "SELECT value FROM runtime_meta WHERE key = 'started_at'"
    ).fetchone()
    if not r or not r["value"]:
        return None
    return datetime.fromisoformat(r["value"].replace("Z", "+00:00"))


def mark_clusterer_run(db) -> None:
    db._conn.execute(
        """
        INSERT INTO runtime_meta (key, value) VALUES ('last_clusterer_run', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (datetime.now(timezone.utc).isoformat(timespec="seconds"),),
    )
    db._conn.commit()


# --- meta-loop: Infrastructure Graph convergence digest ---


def run_infra_convergence(db, fraction: float = 0.5):
    """Build the Infrastructure Graph from current infrastructure_ops rows.

    This is the deterministic core of the v2 meta-loop. For every
    internal_platform slot (the controlled INTERNAL_PLATFORMS vocab) we:

      1. group the per-startup infrastructure_ops rows,
      2. canonicalize each platform group into one InfrastructureNode row
         (canonical name = "<platform> layer"),
      3. emit an InfrastructureEdge per startup sighting, picking the edge
         kind from the broader_applicability flag:
           broader_applicability=1  -> 'needs'  (analyst flagged this is a
                                              shared layer the startup lacks)
           broader_applicability=0  -> 'builds' (the startup built it
                                              internally, a re-implementation
                                              signal that the layer is being
                                              rebuilt by every team)
      4. run decisions.infra_convergence_gate against each node's sightings
         and the analysed-cohort size, flipping the convergence flag where it
         fires.

    Returns the digest the PM prints to the user: a list of nodes sorted by
    sightings desc, annotated with the converged bool and which startups back
    each sighting. Idempotent — re-running rebuilds the graph from current
    infrastructure_ops; we keep edges (they're UNIQUE on startup+node+type+
    source).
    """
    from idea_factory.decisions import infra_convergence_gate
    from idea_factory.schema import (
        InfrastructureEdgeRow,
        InfrastructureNodeRow,
    )

    grouped = db.infrastructure_ops_grouped_by_platform()
    cohort = db.count_analysed_startups()
    digest = []
    for platform, raw_sightings in grouped.items():
        if not raw_sightings:
            continue  # defensive: skip empty platform slots
        canonical = f"{platform} layer"

        # Upsert the node ONCE per platform to get its id; we update its
        # sightings/convergence columns with a single follow-up upsert at
        # the end of this loop iteration (avoids N redundant upserts for an
        # N-startup sighting list, and gives a clean single-source-of-truth
        # write per node per pass).
        node_id = db.upsert_infrastructure_node(InfrastructureNodeRow(
            canonical_name=canonical,
            internal_platform=platform,
            aliases=[platform],
            sightings=0,
            clusters_seen=[],
            convergence=False,
            mini_spec=None,
        ))

        seen_startups: set[int] = set()
        for startup_id, _name, broader in raw_sightings:
            edge_kind = "needs" if broader else "builds"
            db.insert_infrastructure_edge(InfrastructureEdgeRow(
                startup_id=startup_id,
                infra_node_id=node_id,
                edge_type=edge_kind,
                source_ref=f"infra_ops:{platform}",
            ))
            seen_startups.add(startup_id)

        # Cross-cluster coverage: which ICP clusters do those startups hang off?
        seen_clusters: set[str] = set()
        if seen_startups:
            placeholders = ",".join("?" * len(seen_startups))
            rows = db._conn.execute(
                f"""
                SELECT DISTINCT ms.icp_cluster FROM startups s
                JOIN candidate_startups cs ON cs.website = s.website
                JOIN market_segments ms ON ms.id = cs.market_segment_id
                WHERE s.id IN ({placeholders})
                """,
                tuple(seen_startups),
            ).fetchall()
            for r in rows:
                if r["icp_cluster"]:
                    seen_clusters.add(r["icp_cluster"])

        g = infra_convergence_gate(
            sightings=len(seen_startups),
            cohort_size=cohort,
            distinct_clusters=len(seen_clusters),
            fraction=fraction,
        )
        # Single update per node with the final sightings + convergence flag.
        db.upsert_infrastructure_node(InfrastructureNodeRow(
            canonical_name=canonical,
            internal_platform=platform,
            aliases=[platform],
            sightings=g.sightings,
            clusters_seen=sorted(seen_clusters),
            convergence=g.converged,
            mini_spec=None,
        ))
        digest.append({
            "node": canonical,
            "platform": platform,
            "sightings": g.sightings,
            "cohort": g.cohort_size,
            "threshold": g.threshold,
            "convergence": g.converged,
            "clusters": sorted(seen_clusters),
            "startups": [n for _, n in db.infrastructure_node_sightings(node_id)],
        })
    digest.sort(key=lambda d: (-d["sightings"], d["node"]))
    return digest