"""Deterministic gates that sit between DAG nodes.

These are the only places where routing decisions get made. Agents return prose
and receipts; they do not get to decide who runs next. Every function here is
pure (no DB writes, no IO) and typed: input is the agent's receipt or the
candidate rows, output is the routing decision.

If an agent wants to override one of these gates, it can't. It returns a
`blocked` receipt and a human edits decisions.py or founder-profile.md.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from idea_factory.schema import (
    ICP_CLUSTERS,
    PersonalFitRow,
    ProblemEdgeRow,
    ValidatorReceipt,
    WedgeRow,
)


# --- between Analyst node and Scorer node: evidence gate ---


@dataclass(frozen=True)
class EvidenceGate:
    accepted: list[WedgeRow]
    rejected: list[WedgeRow]


def evidence_gate(wedges: list[WedgeRow]) -> EvidenceGate:
    """No-evidence wedges die. A wedge with NULL evidence is auto-disqualified.

    The analyst emits 20+ wedge rows; some have evidence citations, some are
    explicit no-need rows (NULL description + one-line reason). Both are kept,
    but only rows with NON-NULL evidence AND NON-NULL description pass to the
    scorer; everything else is retained as context but cannot be selected.
    """
    accepted, rejected = [], []
    for w in wedges:
        if w.evidence and w.description:
            accepted.append(w)
        else:
            rejected.append(w)
    return EvidenceGate(accepted=accepted, rejected=rejected)


# --- between Scorer node and Validator node: wedge rank ---


def rank_wedges_by_fit(
    wedges: list[WedgeRow], fit: PersonalFitRow
) -> list[tuple[WedgeRow, float]]:
    """Pure function. Returns wedges sorted by fit * evidence-tightness weight.

    weight = (fit.total / 80) * 0.6 + evidence_tightness * 0.4
    evidence_tightness=1.0 for wedges with a citation, 0.0 otherwise.

    The validator receives the top wedge per startup from this ranking. No prose.
    """
    fit_total = fit.total if fit.total is not None else sum(
        [
            fit.technical_advantage, fit.interest, fit.existing_knowledge,
            fit.sales_ability, fit.long_term_moat, fit.build_speed,
            fit.market_size, fit.distribution_fit,
        ]
    )
    fit_norm = fit_total / 80.0
    ranked: list[tuple[WedgeRow, float]] = []
    for w in wedges:
        if not (w.evidence and w.description):
            continue
        ev_tight = 1.0 if w.evidence else 0.0
        score = (fit_norm * 0.6) + (ev_tight * 0.4)
        ranked.append((w, round(score, 4)))
    ranked.sort(key=lambda t: t[1], reverse=True)
    return ranked


def top_wedge(
    wedges: list[WedgeRow], fit: PersonalFitRow
) -> Optional[WedgeRow]:
    ranked = rank_wedges_by_fit(wedges, fit)
    return ranked[0][0] if ranked else None


# --- between Validator node and Builder node: graduation gate ---


# Honour rules from the orchestrator:
# - graduate only if reply_rate >= 5% across 30+ sends AND 3+ pain-signal replies
MIN_SENDS = 30
MIN_REPLY_RATE = 0.05
MIN_PAIN_REPLIES = 3
MIN_FIT_TO_VALIDATE = 60


def should_validate(fit: PersonalFitRow) -> bool:
    """Skip outreach for low-fit startups (saves the cold-reachable budget)."""
    fit_total = fit.total if fit.total is not None else 0
    return fit_total >= MIN_FIT_TO_VALIDATE


@dataclass(frozen=True)
class GateResult:
    graduated: bool
    reason: str
    reply_rate: float


def graduation_gate(
    sends: int,
    pain_signal_replies: int,
    replies: int,
) -> GateResult:
    """Pure decision. Drives the PM's `stage_marker='graduated'` write."""
    if sends < MIN_SENDS:
        return GateResult(
            graduated=False,
            reason=f"insufficient sends ({sends}<{MIN_SENDS})",
            reply_rate=0.0,
        )
    reply_rate = replies / sends if sends else 0.0
    if reply_rate < MIN_REPLY_RATE:
        return GateResult(
            graduated=False,
            reason=(
                f"reply rate {reply_rate:.1%} below {MIN_REPLY_RATE:.0%}; "
                "wedge-selection is broken, not outreach copy. Re-tune founder history."
            ),
            reply_rate=reply_rate,
        )
    if pain_signal_replies < MIN_PAIN_REPLIES:
        return GateResult(
            graduated=False,
            reason=(
                f"only {pain_signal_replies} pain-signal replies "
                f"(need {MIN_PAIN_REPLIES}); keep waiting or re-wedge."
            ),
            reply_rate=reply_rate,
        )
    return GateResult(
        graduated=True,
        reason=f"graduated: {reply_rate:.1%} reply rate, {pain_signal_replies} pain replies",
        reply_rate=reply_rate,
    )


# --- kill metric (orchestrator halts the loop) ---


KILL_METRIC_WEEKS = 8


def kill_metric_triggered(
    started_at: datetime,
    now: datetime,
    pain_replies_across_all_wedges: int,
) -> bool:
    """After KILL_METRIC_WEEKS of runtime with no wedge reaching MIN_PAIN_REPLIES,
    the loop halts. Re-tune founder history before resuming; do not iterate
    outreach copy."""
    age = now - started_at
    if age < timedelta(weeks=KILL_METRIC_WEEKS):
        return False
    return pain_replies_across_all_wedges < MIN_PAIN_REPLIES


# --- between Clusterer writes and Pattern Library: promotion gate ---


MIN_SIGHTINGS = 3
MIN_CLUSTERS = 2


def promotion_gate(
    sightings: int,
    clusters_seen: list[str],
) -> bool:
    """Promote to Pattern Library only when:
    - 3+ sightings across non-adjacent markets spanning 2+ of the 3 ICP clusters
    Within-cluster repeats are noise; cross-cluster repeats are signal.
    """
    if sightings < MIN_SIGHTINGS:
        return False
    distinct_valid = {c for c in clusters_seen if c in ("developer", "infra", "enterprise-IT")}
    return len(distinct_valid) >= MIN_CLUSTERS


# --- clusterer: fixed edge vocabulary enforcement ---


ALLOWED_EDGE_TYPES = {
    "solves", "sub-problem-of", "suffers-from",
    "enables", "incumbent-of", "OSS-alternative-to",
}


def classify_edge(edge_type: str) -> Optional[str]:
    """Returns the canonical edge type or None if not allowed.
    The clusterer MUST call this before inserting a problem_edges row.
    Free-form edges are forbidden -> the agent surface them in remaining_blockers.
    """
    if edge_type in ALLOWED_EDGE_TYPES:
        return edge_type
    return None


# --- clusterer: pattern retire rule ---


RETIRE_ZERO_GROWTH_DAYS = 30


def should_retire_pattern(
    last_growth_rate: Optional[int],
    last_promoted_at: Optional[datetime],
    now: datetime,
) -> bool:
    """Retire patterns with <=0 growth for 30+ days. Saturated == noise."""
    if last_growth_rate is None or last_growth_rate > 0:
        return False
    if last_promoted_at is None:
        return False
    return (now - last_promoted_at) >= timedelta(days=RETIRE_ZERO_GROWTH_DAYS)


# --- dispatcher: route a validator receipt to the next node ---


def route_after_validator(receipt: ValidatorReceipt) -> Optional[str]:
    """If receipt says graduated, route to builder (06). Else wait or halt."""
    if receipt.kill_metric_triggered:
        return None  # halt: re-tune founder history, do not auto-resume
    if receipt.graduated:
        return "06"
    return None  # PM either waits for more replies or re-dispatches validator


# --- honor rule: builder rejects wedges the validator did not graduate ---


def builder_accepts(
    wedge_id: int,
    pain_reply_rows: int,
    startup_stage_marker: Optional[str],
) -> tuple[bool, str]:
    """Builder's hard precondition. Validation before build, non-negotiable."""
    if startup_stage_marker != "graduated":
        return False, f"startup stage is {startup_stage_marker!r}, must be 'graduated'"
    if pain_reply_rows < MIN_PAIN_REPLIES:
        return False, f"only {pain_reply_rows} pain replies, need {MIN_PAIN_REPLIES}"
    return True, "accepted"