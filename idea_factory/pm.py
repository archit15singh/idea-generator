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

CANONICAL_MARKETS = [
    "AI Engineering",
    "Cybersecurity",
    "Enterprise AI",
    "Developer Tools",
    "Knowledge Management",
    "AI Infrastructure",
    "Agent Infrastructure",
    "Enterprise Automation",
    "B2B Productivity",
    "Technical Founder Tools",
]


def default_scout_input(depth: int = 2) -> MarketScoutInput:
    """The DAG's entry point. The PM hands this to the market scout."""
    return MarketScoutInput(markets=CANONICAL_MARKETS, depth=depth)


# --- HTML-to-text helper: shrink webfetch footprint before reasoning ---

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def html_to_summary(html: str, max_chars: int = 1200) -> str:
    """Strip tags, collapse whitespace, truncate. For ingestor pre-processing.

    webfetch returns 60KB+ of marketing copy per startup. Without this, a
    5-startup cohort blows the context budget before SID extraction even
    starts. The ingestor reasons over the summary, not the raw page.
    """
    no_tags = _TAG_RE.sub(" ", html)
    collapsed = _WS_RE.sub(" ", no_tags).strip()
    if len(collapsed) > max_chars:
        collapsed = collapsed[:max_chars] + " ...[truncated]"
    return collapsed


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
    for platform, sightings in grouped.items():
        # one canonical node per platform slot
        canonical = f"{platform} layer"
        node_id = db.upsert_infrastructure_node(InfrastructureNodeRow(
            canonical_name=canonical,
            internal_platform=platform,
            aliases=[platform],
            sightings=0,
            clusters_seen=[],
            convergence=False,
            mini_spec=None,
        ))
        seen_startups = set()
        seen_clusters = set()
        for startup_id, _name, broader in sightings:
            edge_kind = "needs" if broader else "builds"
            db.insert_infrastructure_edge(InfrastructureEdgeRow(
                startup_id=startup_id,
                infra_node_id=node_id,
                edge_type=edge_kind,
                source_ref=f"infra_ops:{platform}",
            ))
            seen_startups.add(startup_id)
        # cross-cluster via the originating market segment of each startup
        rows = db._conn.execute(
            """
            SELECT DISTINCT ms.icp_cluster FROM startups s
            JOIN candidate_startups cs ON cs.website = s.website
            JOIN market_segments ms ON ms.id = cs.market_segment_id
            WHERE s.id IN (%s)
            """ % ",".join("?" * len(seen_startups)),
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