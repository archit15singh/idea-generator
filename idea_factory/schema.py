"""Typed schemas for every DAG node boundary in the idea-factory skill.

The skill orchestrator (SKILL.md) IS the DAG. The subagents ARE the nodes.
This module defines the typed input and output at every node boundary so:
- the PM can validate an agent's JSON receipt before routing to the next node
- deterministic gates (decisions.py) sit between nodes and never trust prose
- the DB layer (db.py) round-trips typed rows, not bare dicts

Naming convention: <Node><Kind> where Kind ∈ {Input, Receipt, Row, Payload}.
e.g. IngestorInput, IngestorReceipt, WedgeRow, RecursivePathPayload.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator


# --- Controlled vocabularies (closed sets; agents must not invent values) ---


WEDGE_TYPES = Literal[
    "Smaller ICP",
    "Different geography",
    "Better UX",
    "Open source",
    "Self-hosted",
    "Compliance-first",
    "Cheaper",
    "Faster",
    "More accurate",
    "AI-native",
    "Vertical-specific",
    "Developer-first",
    "Enterprise-first",
    "SMB-first",
    "API-first",
    "Offline/local-first",
    "Mobile-first",
    "Better integrations",
    "Better memory",
    "Better evaluation",
]

INTERNAL_PLATFORMS = Literal[
    "Evaluation",
    "Prompt management",
    "Memory",
    "Authentication",
    "Connectors",
    "Knowledge graph",
    "Scheduling",
    "Cost optimization",
    "Tracing/observability",
    "Retrieval/RAG",
]

EDGE_TYPES = Literal[
    "solves",
    "sub-problem-of",
    "suffers-from",
    "enables",
    "incumbent-of",
    "OSS-alternative-to",
]

ICP_CLUSTERS = Literal["developer", "infra", "enterprise-IT"]

STAGE_MARKERS = Literal[
    "scouted",
    "ingested",
    "analysed",
    "scored",
    "validated",
    "graduated",
    "built",
]


class Result(str, Enum):
    done = "done"
    blocked = "blocked"
    partial = "partial"


# --- Persistent domain rows (mirror templates/schema.sql) ---


class StartupRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Optional[int] = None
    startup: str
    website: str
    yc_batch: Optional[str] = None
    founders: Optional[list[str]] = None
    category: Optional[str] = None
    funding: Optional[str] = None
    open_source: Optional[bool] = None
    pricing: Optional[str] = None
    stage: Optional[str] = None
    stage_marker: Optional[STAGE_MARKERS] = None
    source_url: Optional[str] = None
    raw: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CustomerRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    startup_id: int
    icp: Optional[str] = None
    company_size: Optional[str] = None
    buyer_persona: Optional[str] = None
    economic_buyer: Optional[str] = None
    user: Optional[str] = None


class ProblemRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    startup_id: int
    core_problem: Optional[str] = None
    existing_alternatives: Optional[str] = None
    why_current_fail: Optional[str] = None
    cost_of_not_solving: Optional[str] = None


class ProductRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    startup_id: int
    core_workflow: Optional[str] = None
    key_features: Optional[str] = None
    ai_capabilities: Optional[str] = None
    integrations: Optional[str] = None


class GTMRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    startup_id: int
    landing_page: Optional[str] = None
    positioning: Optional[str] = None
    pricing: Optional[str] = None
    sales_motion: Optional[str] = None
    plg_or_sales: Optional[str] = None
    distribution_channels: Optional[str] = None


class TechnicalRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    startup_id: int
    likely_architecture: Optional[str] = None
    llms: Optional[str] = None
    memory: Optional[str] = None
    agents: Optional[str] = None
    vector_db: Optional[str] = None
    evaluation: Optional[str] = None
    observability: Optional[str] = None


class CompetitiveRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    startup_id: int
    direct_competitors: Optional[str] = None
    indirect_competitors: Optional[str] = None
    oss_alternatives: Optional[str] = None
    moat: Optional[str] = None
    weaknesses: Optional[str] = None


class RecursivePathRow(BaseModel):
    """Output of the analyst's recursive descent (L1-L10). Stored as one row."""

    model_config = ConfigDict(extra="forbid")
    startup_id: int
    l1: Optional[str] = None
    l2: Optional[str] = None
    l3: Optional[str] = None
    l4: Optional[str] = None
    l5: Optional[str] = None
    l6: Optional[str] = None
    l7: Optional[str] = None
    l8: Optional[str] = None
    l9: Optional[str] = None
    l10: Optional[str] = None
    l5_shifts: list[str] = Field(default_factory=list)


class WedgeRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: Optional[int] = None
    startup_id: int
    wedge_type: WEDGE_TYPES
    description: Optional[str] = None
    evidence: Optional[str] = None
    personal_fit_score: Optional[int] = Field(default=None, ge=0, le=100)
    selected: bool = False
    created_at: Optional[datetime] = None

    @field_validator("evidence")
    @classmethod
    def evidence_not_placeholder(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v.strip() == "":
            return None
        return v


class InfrastructureOpRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: Optional[int] = None
    startup_id: int
    internal_platform: INTERNAL_PLATFORMS
    description: Optional[str] = None
    broader_applicability: bool = False
    evidence: Optional[str] = None


class PersonalFitRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    startup_id: int
    technical_advantage: int = Field(ge=0, le=10)
    interest: int = Field(ge=0, le=10)
    existing_knowledge: int = Field(ge=0, le=10)
    sales_ability: int = Field(ge=0, le=10)
    long_term_moat: int = Field(ge=0, le=10)
    build_speed: int = Field(ge=0, le=10)
    market_size: int = Field(ge=0, le=10)
    distribution_fit: int = Field(ge=0, le=10)
    total: Optional[int] = Field(default=None, ge=0, le=80)
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None

    def model_post_init(self, __ctx) -> None:
        if self.total is None:
            object.__setattr__(
                self,
                "total",
                sum(
                    [
                        self.technical_advantage,
                        self.interest,
                        self.existing_knowledge,
                        self.sales_ability,
                        self.long_term_moat,
                        self.build_speed,
                        self.market_size,
                        self.distribution_fit,
                    ]
                ),
            )


class OutreachLogRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: Optional[int] = None
    wedge_id: int
    startup_id: int
    message_id: Optional[str] = None
    sent_at: Optional[datetime] = None
    replied_at: Optional[datetime] = None
    reply_pain_signal: bool = False
    prospect_persona: Optional[str] = None


class WaitlistRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: Optional[int] = None
    wedge_id: int
    source: Optional[str] = None
    referrer: Optional[str] = None
    icp_attributed: Optional[str] = None
    pricing_variant: Optional[str] = None
    signed_up_at: Optional[datetime] = None


class PatternLibraryRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: Optional[int] = None
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    sightings: int = 0
    last_growth_rate: Optional[int] = None
    last_promoted_at: Optional[datetime] = None
    retired_at: Optional[datetime] = None
    mini_spec: Optional[str] = None


class ProblemNodeRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: Optional[int] = None
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None


class ProblemEdgeRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: Optional[int] = None
    from_node: int
    to_node: int
    edge_type: EDGE_TYPES
    source_ref: Optional[str] = None
    created_at: Optional[datetime] = None


# --- Node inputs (what the PM hands each subagent) ---


class MarketScoutInput(BaseModel):
    """Handed to idea-factory-market-scout. The entry point of the whole DAG.

    The DAG starts from markets, never from a flat startup list. The scout
    recursively breaks each market into sub-markets and emits candidate YC
    startups per sub-market. The ingestor (node 01) fans out on the receipts.
    """

    model_config = ConfigDict(extra="forbid")
    markets: list[str] = Field(min_length=1)
    depth: int = Field(default=2, ge=1, le=3)


class MarketSegmentRow(BaseModel):
    """A sub-market produced by the scout. Candidate startups hang off this."""

    model_config = ConfigDict(extra="forbid")
    id: Optional[int] = None
    parent_market: str
    segment_name: str
    icp_cluster: ICP_CLUSTERS
    rationale: Optional[str] = None


class CandidateStartupRow(BaseModel):
    """A YC startup candidate emitted by the scout for a segment.

    The ingestor will UPSERT this into `startups` keyed on `website`; the
    `market_segment_id` link is carried through so wedges can later map back
    to the originating market segment for cross-cluster counting.
    """

    model_config = ConfigDict(extra="forbid")
    name: str
    website: str
    market_segment_id: int
    yc_batch: Optional[str] = None
    notes: Optional[str] = None


class MarketScoutReceiptStub(BaseModel):
    """Forward declaration shape. The real MarketScoutReceipt lives in the
    receipts section; using it here would require BaseReceipt to be defined
    first. Instead, the scout returns a dict the PM parses with
    `receipts.parse`. See MarketScoutReceipt below."""

    model_config = ConfigDict(extra="forbid")
    markets_processed: int = Field(ge=0)
    segments_created: int = Field(ge=0)
    candidates_emitted: int = Field(ge=0)


class IngestorInput(BaseModel):
    """Handed to idea-factory-ingestor. The PM picks the cohort."""

    model_config = ConfigDict(extra="forbid")
    startup_domains: list[str] = Field(min_length=1)
    cohort_id: str


class AnalystInput(BaseModel):
    """Handed to idea-factory-analyst. One startup at a time."""

    model_config = ConfigDict(extra="forbid")
    startup_id: int
    sid: StartupRow
    customer: Optional[CustomerRow] = None
    problem: Optional[ProblemRow] = None
    product: Optional[ProductRow] = None
    gtm: Optional[GTMRow] = None
    technical: Optional[TechnicalRow] = None
    competitive: Optional[CompetitiveRow] = None


class ScorerInput(BaseModel):
    """Handed to idea-factory-scorer. Reads founder profile + wedges."""

    model_config = ConfigDict(extra="forbid")
    startup_id: int
    wedges: list[WedgeRow] = Field(min_length=1)
    founder_profile_path: str
    existing_fit: Optional[PersonalFitRow] = None  # if reviewed_at set, skip


class ValidatorInput(BaseModel):
    """Handed to idea-factory-validator. Top wedge already selected by decisions.py."""

    model_config = ConfigDict(extra="forbid")
    startup_id: int
    wedge: WedgeRow
    personal_fit: PersonalFitRow
    prospect_persona_hint: Optional[str] = None


class BuilderInput(BaseModel):
    """Handed to idea-factory-builder. Only graduated wedges reach here."""

    model_config = ConfigDict(extra="forbid")
    startup_id: int
    wedge: WedgeRow
    pain_replies: list[OutreachLogRow] = Field(min_length=3)
    sid: StartupRow


class ClustererInput(BaseModel):
    """Handed to idea-factory-clusterer. Whole-DB pass, not per startup."""

    model_config = ConfigDict(extra="forbid")
    min_new_since_last: int = Field(default=20, ge=1)
    last_run_at: Optional[datetime] = None


# --- Node receipts (what each subagent returns; PM validates + routes) ---


STAGE_VALUES = {"00", "01", "02", "04", "05", "06", "07"}
NEXT_STAGE_VALUES = {"01", "02", "04", "05", "06", "07", "08", None}
STAGE_DEFAULTS = {
    "IngestorReceipt": "01",
    "AnalystReceipt": "02",
    "ScorerReceipt": "04",
    "ValidatorReceipt": "05",
    "BuilderReceipt": "06",
    "ClustererReceipt": "07",
}


class BaseReceipt(BaseModel):
    """Common shape. Every receipt in the DAG carries these fields.

    `stage` and `next_stage` are str-typed (not narrowed Literals) so subclasses
    can set per-stage defaults without tripping Python's invariance rule on
    mutable fields. Values are constrained at parse time by field_validator.
    """

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["idea_factory_receipt_v1"] = "idea_factory_receipt_v1"
    result: Result
    stage: str
    startup_ids: list[int] = Field(default_factory=list)
    changed_rows: int = Field(ge=0)
    summary: str = Field(max_length=240)
    remaining_blockers: list[str] = Field(default_factory=list)
    next_stage: Optional[str] = None

    @field_validator("stage")
    @classmethod
    def _check_stage(cls, v: str) -> str:
        if v not in STAGE_VALUES:
            raise ValueError(f"stage must be one of {sorted(STAGE_VALUES)}, got {v!r}")
        return v

    @field_validator("next_stage")
    @classmethod
    def _check_next_stage(cls, v: Optional[str]) -> Optional[str]:
        if v not in NEXT_STAGE_VALUES:
            raise ValueError(
                f"next_stage must be one of {sorted(NEXT_STAGE_VALUES - {None})} or None, got {v!r}"
            )
        return v


class IngestorReceipt(BaseReceipt):
    stage: str = "01"
    next_stage: Optional[str] = "02"
    ingested: list[int] = Field(default_factory=list)
    failed: list[str] = Field(default_factory=list)


class AnalystReceipt(BaseReceipt):
    stage: str = "02"
    next_stage: Optional[str] = "04"
    recursive_path: Optional[RecursivePathRow] = None
    wedges_accepted: int = Field(ge=0)
    wedges_rejected: int = Field(ge=0)
    infra_ops_flagged_broader: int = Field(ge=0)
    l5_shift_count: int = Field(ge=0)


class ScorerReceipt(BaseReceipt):
    stage: str = "04"
    next_stage: Optional[str] = "05"
    rows_scored: int = Field(ge=0)
    rows_skipped_human_locked: int = Field(ge=0)
    shape_outliers: list[str] = Field(default_factory=list)


class ValidatorReceipt(BaseReceipt):
    stage: str = "05"
    next_stage: Optional[str] = None
    sends: int = Field(ge=0)
    replies: int = Field(ge=0)
    pain_signal_replies: int = Field(ge=0)
    reply_rate: float = Field(ge=0.0, le=1.0)
    graduated: bool = False
    kill_metric_triggered: bool = False


class BuilderReceipt(BaseReceipt):
    stage: str = "06"
    next_stage: Optional[str] = "07"
    mvp_url: Optional[str] = None
    waitlist_signups: int = Field(ge=0)
    outreach_appended: int = Field(ge=0)
    interviews_scheduled: int = Field(ge=0)


class ClustererReceipt(BaseReceipt):
    stage: str = "07"
    next_stage: Optional[str] = None
    patterns_promoted: list[str] = Field(default_factory=list)
    patterns_retired: list[str] = Field(default_factory=list)
    new_problem_nodes: int = Field(ge=0)
    new_edges: dict[str, int] = Field(default_factory=dict)


class MarketScoutReceipt(BaseReceipt):
    stage: str = "00"
    next_stage: Optional[str] = "01"
    markets_processed: int = Field(ge=0)
    segments_created: int = Field(ge=0)
    candidates_emitted: int = Field(ge=0)
    segments: list[MarketSegmentRow] = Field(default_factory=list)
    candidates: list[CandidateStartupRow] = Field(default_factory=list)


RECEIPT_BY_STAGE = {
    "00": MarketScoutReceipt,
    "01": IngestorReceipt,
    "02": AnalystReceipt,
    "04": ScorerReceipt,
    "05": ValidatorReceipt,
    "06": BuilderReceipt,
    "07": ClustererReceipt,
}