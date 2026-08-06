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
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
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


def seed_for_cluster(cluster: str, limit: int = 5) -> list[tuple[str, str, str, str]]:
    """DEPRECATED. Retained for legacy tests. Real fan-out now goes via the
    market scout to `candidate_startups`, not this hardcoded list."""
    return []


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
        "SELECT MAX(ran_at) AS last FROM runtime_meta WHERE key = 'last_clusterer_run'"
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