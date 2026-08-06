"""Deterministic gates that sit between DAG nodes.

These are the only places where routing decisions get made. Agents return prose
and receipts; they do not get to decide who runs next. Every function here is
pure (no DB writes, no IO) and typed: input is the agent's receipt or the
candidate rows, output is the routing decision.

If an agent wants to override one of these gates, it can't. It returns a
`blocked` receipt and a human edits decisions.py or founder-profile.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, get_args

from idea_factory.schema import (
    ICP_CLUSTERS,
    InfraNodeFitRow,
    PersonalFitRow,
    ValidatorReceipt,
    WedgeRow,
)

# The set of acceptable ICP clusters, derived from the controlled vocabulary
# instead of re-typing the literals here. If `ICP_CLUSTERS` adds a fourth
# cluster, promotion_gate picks it up automatically.
VALID_ICP_CLUSTERS = set(get_args(ICP_CLUSTERS))


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
    distinct_valid = {c for c in clusters_seen if c in VALID_ICP_CLUSTERS}
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


# --- meta-loop: the Infrastructure Graph convergence gate ---

# The single highest-leverage signal the idea-factory can produce: an
# internal platform shows up across enough startups that building THE SHARED
# LAYER beats building any one application of it. Half-the-cohort is the
# threshold (ceil, so a 5-startup cohort needs 3 sightings; a 20-startup
# cohort needs 10). Below the threshold the node is interesting context; at
# or above it, the node becomes a "convergent layer" that the builder should
# be redirected toward instead of the per-startup wedge.

import math as _math


def infra_convergence_threshold(cohort_size: int, fraction: float = 0.5) -> int:
    """Sightings needed for an infra node to be marked convergent.

    Uses ceil so a 5-startup cohort needs 3 sightings, not 2. Cohorts < 2
    never converge (no meta-signal with < 2 sightings).
    """
    if cohort_size < 2:
        return cohort_size + 1  # unreachable
    return int(_math.ceil(cohort_size * fraction))


@dataclass(frozen=True)
class InfraConvergenceResult:
    converged: bool
    sightings: int
    cohort_size: int
    threshold: int
    fraction: float
    distinct_clusters: int


def infra_convergence_gate(
    sightings: int,
    cohort_size: int,
    distinct_clusters: int = 1,
    fraction: float = 0.5,
) -> InfraConvergenceResult:
    """Returns converged=True when an infrastructure node has been sighted
    on >= `fraction` of the analysed cohort (ceil'd) leading in any cluster.

    Requiring cross-cluster coverage is NOT enforced here (unlike
    promotion_gate). The convergence question is "does half the cohort need
    this layer" — a strong intrazone signal is still a convergent layer even
    if it's only one cluster today. Cross-cluster is recorded on the node so
    a PM can layer a stricter `recurring + cross-cluster` filter when needed.
    """
    threshold = infra_convergence_threshold(cohort_size, fraction)
    converged = cohort_size >= 2 and sightings >= threshold
    return InfraConvergenceResult(
        converged=converged,
        sightings=sightings,
        cohort_size=cohort_size,
        threshold=threshold,
        fraction=fraction,
        distinct_clusters=distinct_clusters,
    )


# Infrastructure-edge vocabulary enforcement (mirrors classify_edge for the
# Problem Graph). The clusterer MUST call this before inserting an
# infrastructure_edges row; free-form edge kinds are rejected.
ALLOWED_INFRA_EDGE_TYPES = {"needs", "builds", "uses", "has-gap"}


def classify_infra_edge(edge_type: str) -> Optional[str]:
    if edge_type in ALLOWED_INFRA_EDGE_TYPES:
        return edge_type
    return None


# --- meta-loop: rank convergent infra nodes by founder fit * conviction ---


def rank_infra_nodes_by_fit(
    scored: list[tuple[int, str, InfraNodeFitRow]],
    sightings: dict[int, int],
    clusters: dict[int, int],
    cohort_size: int,
) -> list[tuple[tuple[int, str], float]]:
    """Pure. Returns [(infra_node_id, canonical_name), score] ranked desc.

    score = fit_norm (0..1) * 0.5
          + convergence_norm (sightings/cohort, 0..1) * 0.3
          + cross_cluster_norm (distinct clusters / 3, 0..1) * 0.2

    The v2 conviction loop doesn't just take the best founder fit; it takes
    the best FIT * COHORT-CONVICTION. A node sighted by 8/8 startups that
    scores 0.6 fit beats a 4/8 node that scores 0.9 fit — the recurring
    layer is the bigger opportunity and the founder fit is still real.
    """
    ranked: list[tuple[tuple[int, str], float]] = []
    for node_id, canonical, fit in scored:
        fit_total = fit.total if fit.total is not None else sum(
            [fit.technical_advantage, fit.interest, fit.existing_knowledge,
             fit.sales_ability, fit.long_term_moat, fit.build_speed,
             fit.market_size, fit.distribution_fit]
        )
        fit_norm = fit_total / 80.0
        conv_norm = sightings.get(node_id, 0) / max(cohort_size, 1)
        cluster_norm = min(clusters.get(node_id, 0), 3) / 3.0
        score = (fit_norm * 0.5) + (conv_norm * 0.3) + (cluster_norm * 0.2)
        ranked.append(((node_id, canonical), round(score, 4)))
    ranked.sort(key=lambda t: t[1], reverse=True)
    return ranked


def top_infra_node(
    scored: list[tuple[int, str, InfraNodeFitRow]],
    sightings: dict[int, int],
    clusters: dict[int, int],
    cohort_size: int,
) -> Optional[tuple[int, str]]:
    """The single infrastructure layer to bet on (or None if nothing scored)."""
    ranked = rank_infra_nodes_by_fit(scored, sightings, clusters, cohort_size)
    return ranked[0][0] if ranked else None