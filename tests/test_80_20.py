"""80/20 tests: the crucial 20% of assertions that catch 80% of regressions.

Tests the DAG node boundaries, the deterministic gates, and one end-to-end
flow scenario. Not exhaustive — by design. If any of these go red, something
load-bearing has broken.

Layout:
  - schema contracts (controlled vocabs, computed fields, validation)
  - db layer (idempotent upserts, human-locked immutability)
  - gates (the deterministic routing decisions between nodes)
  - receipts (parse + validate agent JSON returns)
  - end-to-end DAG scenario
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from idea_factory.db import DB
from idea_factory.decisions import (
    ALLOWED_EDGE_TYPES,
    assign_primary_with_global_cap,
    builder_accepts,
    classify_edge,
    evidence_gate,
    graduation_gate,
    infra_convergence_gate,
    infra_convergence_threshold,
    classify_infra_edge,
    kill_metric_triggered,
    promotion_gate,
    route_after_validator,
    should_retire_pattern,
    should_validate,
    shortlist_wedges,
    top_wedge,
    rank_wedges_by_fit,
)
from idea_factory.receipts import parse
from idea_factory.schema import (
    AnalystReceipt,
    BuilderInput,
    CandidateStartupRow,
    ClustererInput,
    CompetitiveRow,
    CustomerRow,
    GTMRow,
    InfrastructureEdgeRow,
    InfrastructureNodeRow,
    InfraNodeFitRow,
    InfraNodeScorerInput,
    IngestorInput,
    IngestorReceipt,
    MarketScoutInput,
    MarketScoutReceipt,
    MarketSegmentRow,
    OutreachLogRow,
    PatternLibraryRow,
    PersonalFitRow,
    ProblemEdgeRow,
    ProblemNodeRow,
    ProblemRow,
    ProductRow,
    ScorerInput,
    StartupRow,
    TechnicalRow,
    ValidatorInput,
    ValidatorReceipt,
    WaitlistRow,
    WedgeRow,
)
from idea_factory.pm import CANONICAL_MARKETS, default_scout_input


# --- schema ---


def test_canonical_markets_seed_is_nonempty():
    assert len(CANONICAL_MARKETS) >= 10
    assert "AI Engineering" in CANONICAL_MARKETS


def test_market_scout_input_rejects_empty_markets():
    with pytest.raises(Exception):
        MarketScoutInput(markets=[])


def test_market_scout_input_depth_bounds():
    with pytest.raises(Exception):
        MarketScoutInput(markets=["AI Engineering"], depth=4)


def test_market_segment_row_rejects_free_form_cluster():
    with pytest.raises(Exception):
        MarketSegmentRow(parent_market="AI Engineering", segment_name="x", icp_cluster="random")


def test_market_scout_receipt_parses_with_stage_00():
    raw = """```json
{"schema_version":"idea_factory_receipt_v1","result":"done","stage":"00","changed_rows":12,"summary":"ok","markets_processed":3,"segments_created":11,"candidates_emitted":30,"segments":[],"candidates":[]}
```"""
    r = parse(raw)
    assert isinstance(r, MarketScoutReceipt)
    assert r.stage == "00"
    assert r.next_stage == "01"


def test_wedge_type_rejects_unknown():
    with pytest.raises(Exception):
        WedgeRow(startup_id=1, wedge_type="Made up", description="d", evidence="c")


def test_wedge_evidence_placeholder_rejected():
    # the evidence validator treats empty/whitespace evidence as NULL
    w = WedgeRow(startup_id=1, wedge_type="Open source", description="d", evidence="   ")
    assert w.evidence is None


def test_personal_fit_total_auto_computes():
    p = PersonalFitRow(
        startup_id=1,
        technical_advantage=10, interest=10, existing_knowledge=2,
        sales_ability=8, long_term_moat=10, build_speed=10,
        market_size=2, distribution_fit=8,
    )
    assert p.total == 60


def test_personal_fit_axis_bounds():
    with pytest.raises(Exception):
        PersonalFitRow(
            startup_id=1,
            technical_advantage=11, interest=0, existing_knowledge=0,
            sales_ability=0, long_term_moat=0, build_speed=0,
            market_size=0, distribution_fit=0,
        )


# --- db ---


@pytest.fixture
def db(tmp_path):
    d = DB(str(tmp_path / "sid.db"))
    d.init()
    yield d
    d.close()


def test_db_market_segment_idempotent(db):
    seg_id = db.upsert_market_segment(MarketSegmentRow(
        parent_market="Agent Infrastructure", segment_name="Agent memory",
        icp_cluster="infra", rationale="ctx across runs",
    ))
    seg_id2 = db.upsert_market_segment(MarketSegmentRow(
        parent_market="Agent Infrastructure", segment_name="Agent memory",
        icp_cluster="infra", rationale="ctx across runs",
    ))
    assert seg_id == seg_id2


def test_db_candidate_startups_fanout(db):
    seg_id = db.upsert_market_segment(MarketSegmentRow(
        parent_market="AI Infrastructure", segment_name="LLM evaluation",
        icp_cluster="developer", rationale="eval harness for agents",
    ))
    db.insert_candidate_startup(CandidateStartupRow(
        name="Braintrust", website="https://www.braintrust.dev",
        market_segment_id=seg_id, yc_batch="W23",
    ))
    db.insert_candidate_startup(CandidateStartupRow(
        name="LangSmith", website="https://smith.langchain.com",
        market_segment_id=seg_id, notes="LangChain's eval/obs",
    ))
    cands = db.candidates_for_ingest()
    assert len(cands) == 2
    # idempotent on website
    db.insert_candidate_startup(CandidateStartupRow(
        name="Braintrust", website="https://www.braintrust.dev",
        market_segment_id=seg_id, yc_batch="W23",
    ))
    assert len(db.candidates_for_ingest()) == 2
    # filtered fan-out
    only_seg = db.candidates_for_ingest(segment_id=seg_id)
    assert len(only_seg) == 2
    # once a candidate is ingested as a startup, it drops out of the fan-out
    db.upsert_startup(StartupRow(
        startup="Braintrust", website="https://www.braintrust.dev", yc_batch="W23",
    ))
    remaining = db.candidates_for_ingest()
    assert len(remaining) == 1
    assert remaining[0].name == "LangSmith"
    assert len(db.candidates_for_ingest(segment_id=seg_id)) == 1


def test_candidates_for_ingest_www_normalized_host(db):
    """www.example.com candidate is excluded when example.com is already a startup."""
    seg_id = db.upsert_market_segment(MarketSegmentRow(
        parent_market="Agent Memory", segment_name="www-dedup",
        icp_cluster="developer", rationale="dedup test",
    ))
    db.upsert_startup(StartupRow(
        startup="Letta", website="https://letta.com", yc_batch="W24",
    ))
    db.insert_candidate_startup(CandidateStartupRow(
        name="Letta www", website="https://www.letta.com",
        market_segment_id=seg_id, yc_batch="W24",
    ))
    db.insert_candidate_startup(CandidateStartupRow(
        name="FreshCo", website="https://fresh.example",
        market_segment_id=seg_id,
    ))
    names = {c.name for c in db.candidates_for_ingest()}
    assert "Letta www" not in names
    assert "FreshCo" in names


def test_candidates_for_ingest_host_aliases(db):
    """HOST_ALIASES: abnormalsecurity.com is covered when abnormal.ai is ingested."""
    from idea_factory.db import HOST_ALIASES

    assert HOST_ALIASES.get("abnormalsecurity.com") == "abnormal.ai"
    assert HOST_ALIASES.get("console.groq.com") == "groq.com"
    seg_id = db.upsert_market_segment(MarketSegmentRow(
        parent_market="Email Security", segment_name="alias-dedup",
        icp_cluster="enterprise-IT", rationale="alias test",
    ))
    db.upsert_startup(StartupRow(
        startup="Abnormal", website="https://abnormal.ai",
    ))
    db.insert_candidate_startup(CandidateStartupRow(
        name="Abnormal Security", website="https://abnormalsecurity.com",
        market_segment_id=seg_id,
    ))
    db.insert_candidate_startup(CandidateStartupRow(
        name="FreshSec", website="https://freshsec.example",
        market_segment_id=seg_id,
    ))
    names = {c.name for c in db.candidates_for_ingest()}
    assert "Abnormal Security" not in names
    assert "FreshSec" in names
    # GroqCloud console host covered when groq.com ingested
    seg2 = db.upsert_market_segment(MarketSegmentRow(
        parent_market="Model Gateways", segment_name="groq-alias",
        icp_cluster="infra", rationale="groq alias",
    ))
    db.upsert_startup(StartupRow(startup="Groq", website="https://groq.com"))
    db.insert_candidate_startup(CandidateStartupRow(
        name="GroqCloud", website="https://console.groq.com",
        market_segment_id=seg2,
    ))
    names2 = {c.name for c in db.candidates_for_ingest()}
    assert "GroqCloud" not in names2


def test_candidates_for_ingest_name_slug_prefix(db):
    """Name-slug prefix: LangSmith skipped when LangSmith Hub already ingested."""
    seg_id = db.upsert_market_segment(MarketSegmentRow(
        parent_market="Observability", segment_name="name-dedup",
        icp_cluster="developer", rationale="name slug test",
    ))
    db.upsert_startup(StartupRow(
        startup="LangSmith Hub", website="https://smith.langchain.com",
    ))
    db.insert_candidate_startup(CandidateStartupRow(
        name="LangSmith", website="https://www.langchain.com/langsmith",
        market_segment_id=seg_id,
    ))
    db.insert_candidate_startup(CandidateStartupRow(
        name="FreshObs", website="https://freshobs.example",
        market_segment_id=seg_id,
    ))
    names = {c.name for c in db.candidates_for_ingest()}
    assert "LangSmith" not in names
    assert "FreshObs" in names


def test_db_idempotent_upsert(db):
    s = StartupRow(startup="Acme", website="https://acme.example", yc_batch="W24")
    id1 = db.upsert_startup(s)
    id2 = db.upsert_startup(s)
    assert id1 == id2


def test_insert_problem_edge_duplicate_returns_false(db):
    a = db.upsert_problem_node(ProblemNodeRow(canonical_name="Node A", aliases=["a"]))
    b = db.upsert_problem_node(ProblemNodeRow(canonical_name="Node B", aliases=["b"]))
    edge = ProblemEdgeRow(from_node=a, to_node=b, edge_type="solves", source_ref="startup:1")
    assert db.insert_problem_edge(edge) is True
    # INSERT OR IGNORE no-op on the same (from_node, to_node, edge_type, source_ref)
    assert db.insert_problem_edge(edge) is False


def test_count_startups_since_counts_same_day_updates(db):
    db.upsert_startup(StartupRow(startup="Acme", website="https://acme.example", yc_batch="W24"))
    # upsert_startup stores updated_at in SQLite space format (datetime('now')),
    # e.g. "2026-08-06 14:33:23"; the boundary is isoformat with T and tz offset.
    # A lexicographic compare would fail (' ' < 'T'); datetime(?) normalizes it.
    boundary = datetime.now(timezone.utc) - timedelta(seconds=2)
    assert db.count_startups_since(boundary) >= 1


def test_db_stage_marker_round_trips(db):
    sid = db.upsert_startup(StartupRow(startup="A", website="https://a.example"))
    db.set_stage_marker(sid, "analysed")
    assert db.get_startup(sid).stage_marker == "analysed"


def test_db_human_locked_personal_fit_is_immutable(db):
    sid = db.upsert_startup(StartupRow(startup="A", website="https://a.example"))
    db.upsert_personal_fit(PersonalFitRow(
        startup_id=sid, technical_advantage=10, interest=10, existing_knowledge=10,
        sales_ability=10, long_term_moat=10, build_speed=10,
        market_size=10, distribution_fit=10,
    ))
    db.lock_personal_fit(sid, "archit")
    wrote = db.upsert_personal_fit(PersonalFitRow(
        startup_id=sid, technical_advantage=1, interest=1, existing_knowledge=1,
        sales_ability=1, long_term_moat=1, build_speed=1,
        market_size=1, distribution_fit=1,
    ))
    assert wrote is False
    assert db.get_personal_fit(sid).total == 80  # not overwritten


def test_db_replace_wedges_is_delete_then_insert(db):
    sid = db.upsert_startup(StartupRow(startup="A", website="https://a.example"))
    db.replace_wedges(sid, [
        WedgeRow(startup_id=sid, wedge_type="Open source", description="d", evidence="c"),
        WedgeRow(startup_id=sid, wedge_type="Cheaper", description="d", evidence="c"),
    ])
    assert len(db.get_wedges(sid)) == 2
    # re-run with 1 wedge; the other must be gone
    db.replace_wedges(sid, [
        WedgeRow(startup_id=sid, wedge_type="Faster", description="d", evidence="c"),
    ])
    ws = db.get_wedges(sid)
    assert len(ws) == 1
    assert ws[0].wedge_type == "Faster"


def test_get_sid_for_analyst_round_trips_all_sections(db):
    sid = db.upsert_startup(StartupRow(
        startup="Letta", website="https://letta.com", yc_batch="W24",
    ))
    db.upsert_customer(CustomerRow(
        startup_id=sid, icp="AI infra eng", company_size="50-500",
        buyer_persona="eng lead", economic_buyer="VP eng", user="platform team",
    ))
    db.upsert_problem(ProblemRow(
        startup_id=sid, core_problem="context loss across sessions",
        existing_alternatives="vector DBs", why_current_fail="no memory layer",
        cost_of_not_solving="rewrites",
    ))
    db.upsert_product(ProductRow(
        startup_id=sid, core_workflow="agent loop",
        key_features="persistent memory", ai_capabilities="auto-summarise",
        integrations="langchain",
    ))
    db.upsert_gtm(GTMRow(
        startup_id=sid, landing_page="https://letta.com",
        positioning="agent memory", pricing="usage-based",
        sales_motion="PLG", plg_or_sales="plg",
        distribution_channels="OSS, docs",
    ))
    db.upsert_technical(TechnicalRow(
        startup_id=sid, likely_architecture="RAG over session logs",
        llms="gpt-4", memory="managed block store", agents="letta agents",
        vector_db="pgvector", evaluation="offline suite",
        observability="tracing",
    ))
    db.upsert_competitive(CompetitiveRow(
        startup_id=sid, direct_competitors="MemGPT",
        indirect_competitors="vector DBs", oss_alternatives="LangChain memory",
        moat="OSS lineage", weaknesses="no SOC 2",
    ))
    a = db.get_sid_for_analyst(sid)
    assert a.startup_id == sid
    assert a.sid.startup == "Letta"
    assert a.customer is not None and a.customer.icp == "AI infra eng"
    assert a.problem is not None and a.problem.core_problem == "context loss across sessions"
    assert a.product is not None and a.product.core_workflow == "agent loop"
    assert a.gtm is not None and a.gtm.positioning == "agent memory"
    assert a.technical is not None and a.technical.llms == "gpt-4"
    assert a.competitive is not None and a.competitive.moat == "OSS lineage"


# --- pm: typed input builders ---


def test_build_clusterer_input_no_crash(db):
    from idea_factory.pm import build_clusterer_input, mark_clusterer_run

    before = build_clusterer_input(db)
    assert isinstance(before, ClustererInput)
    assert before.last_run_at is None
    mark_clusterer_run(db)
    after = build_clusterer_input(db)
    assert isinstance(after, ClustererInput)
    assert after.last_run_at is not None


def test_build_scorer_input_round_trips(db):
    from idea_factory.pm import build_scorer_input

    sid = db.upsert_startup(StartupRow(startup="A", website="https://a.example"))
    db.replace_wedges(sid, [
        WedgeRow(startup_id=sid, wedge_type="Open source", description="d", evidence="c"),
    ])
    inp = build_scorer_input(db, sid, founder_profile_path="skill/templates/founder-profile.md")
    assert isinstance(inp, ScorerInput)
    assert inp.startup_id == sid
    assert len(inp.wedges) == 1
    assert inp.founder_profile_path == "skill/templates/founder-profile.md"


def test_build_validator_input_round_trips(db):
    from idea_factory.pm import build_validator_input

    sid = db.upsert_startup(StartupRow(startup="A", website="https://a.example"))
    db.replace_wedges(sid, [
        WedgeRow(startup_id=sid, wedge_type="Open source", description="d", evidence="c"),
    ])
    wedge = db.get_wedges(sid)[0]
    db.upsert_personal_fit(PersonalFitRow(
        startup_id=sid, technical_advantage=5, interest=5, existing_knowledge=5,
        sales_ability=5, long_term_moat=5, build_speed=5,
        market_size=5, distribution_fit=5,
    ))
    inp = build_validator_input(db, sid, wedge.id)
    assert isinstance(inp, ValidatorInput)
    assert inp.startup_id == sid
    assert inp.wedge.id == wedge.id
    assert inp.personal_fit is not None


# --- gates: evidence ---


def test_evidence_gate_drops_no_evidence():
    eg = evidence_gate([
        WedgeRow(startup_id=1, wedge_type="Open source", description="d", evidence="c.moat=NULL"),
        WedgeRow(startup_id=1, wedge_type="Cheaper", description="d", evidence=None),
        WedgeRow(startup_id=1, wedge_type="Faster", description=None, evidence="c.moat=NULL"),
    ])
    assert len(eg.accepted) == 1
    assert eg.accepted[0].wedge_type == "Open source"
    assert len(eg.rejected) == 2


# --- gates: wedge ranking + selection ---


def test_top_wedge_picks_highest_combined_score():
    fit = PersonalFitRow(
        startup_id=1,
        technical_advantage=10, interest=10, existing_knowledge=10,
        sales_ability=10, long_term_moat=10, build_speed=10,
        market_size=10, distribution_fit=10,
    )
    wedges = [
        WedgeRow(id=1, startup_id=1, wedge_type="Open source", description="d", evidence="c"),
        WedgeRow(id=2, startup_id=1, wedge_type="Cheaper", description="d", evidence=None),
    ]
    # only the evidence-bearing wedge survives ranking
    ranked = rank_wedges_by_fit(wedges, fit)
    assert len(ranked) == 1
    assert ranked[0][0].wedge_type == "Open source"
    top = top_wedge(wedges, fit)
    assert top is not None
    assert top.wedge_type == "Open source"


def test_rank_wedges_prefers_per_wedge_personal_fit_score():
    """Without per-wedge scores every evidence row collides at the same rank.

    The scorer writes wedges.personal_fit_score (0-100); top_wedge must honour
    it or validator outreach is an insertion-order lottery.
    """
    fit = PersonalFitRow(
        startup_id=1,
        technical_advantage=8, interest=8, existing_knowledge=8,
        sales_ability=8, long_term_moat=8, build_speed=8,
        market_size=8, distribution_fit=8,  # total=64, startup_fit_norm=0.8
    )
    wedges = [
        WedgeRow(
            id=1, startup_id=1, wedge_type="Cheaper", description="low align",
            evidence="c.pricing", personal_fit_score=40,
        ),
        WedgeRow(
            id=2, startup_id=1, wedge_type="Open source", description="home turf",
            evidence="c.moat=OSS", personal_fit_score=92,
        ),
        WedgeRow(
            id=3, startup_id=1, wedge_type="Self-hosted", description="mid",
            evidence="c.weaknesses", personal_fit_score=70,
        ),
    ]
    ranked = rank_wedges_by_fit(wedges, fit)
    assert [w.wedge_type for w, _ in ranked] == ["Open source", "Self-hosted", "Cheaper"]
    # high wedge score beats startup-level fallback even when startup fit is high
    assert ranked[0][1] > ranked[1][1] > ranked[2][1]
    assert top_wedge(wedges, fit).wedge_type == "Open source"


def test_rank_wedges_falls_back_to_startup_fit_when_wedge_unscored():
    fit = PersonalFitRow(
        startup_id=1,
        technical_advantage=10, interest=10, existing_knowledge=10,
        sales_ability=10, long_term_moat=10, build_speed=10,
        market_size=10, distribution_fit=10,  # total=80
    )
    wedges = [
        WedgeRow(id=1, startup_id=1, wedge_type="Open source", description="d", evidence="c"),
        WedgeRow(id=2, startup_id=1, wedge_type="Faster", description="d", evidence="c"),
    ]
    ranked = rank_wedges_by_fit(wedges, fit)
    assert len(ranked) == 2
    # both unscored -> equal primary score (startup fit * 0.6 + 0.4 = 1.0)
    assert ranked[0][1] == ranked[1][1] == 1.0


def test_top_wedge_returns_none_when_all_lack_evidence():
    fit = PersonalFitRow(
        startup_id=1,
        technical_advantage=5, interest=5, existing_knowledge=5,
        sales_ability=5, long_term_moat=5, build_speed=5,
        market_size=5, distribution_fit=5,
    )
    ws = [WedgeRow(startup_id=1, wedge_type="Cheaper", description="d", evidence=None)]
    assert top_wedge(ws, fit) is None


def test_shortlist_wedges_enforces_type_diversity():
    fit = PersonalFitRow(
        startup_id=1,
        technical_advantage=8, interest=8, existing_knowledge=8,
        sales_ability=8, long_term_moat=8, build_speed=8,
        market_size=8, distribution_fit=8,
    )
    wedges = [
        WedgeRow(id=1, startup_id=1, wedge_type="Better memory", description="m1",
                 evidence="e", personal_fit_score=97),
        WedgeRow(id=2, startup_id=1, wedge_type="Better memory", description="m2",
                 evidence="e", personal_fit_score=96),
        WedgeRow(id=3, startup_id=1, wedge_type="Open source", description="o",
                 evidence="e", personal_fit_score=80),
        WedgeRow(id=4, startup_id=1, wedge_type="Developer-first", description="d",
                 evidence="e", personal_fit_score=70),
    ]
    sl = shortlist_wedges(wedges, fit, k=3, max_per_type=1)
    types = [w.wedge_type for w, _ in sl]
    assert types == ["Better memory", "Open source", "Developer-first"]
    assert types.count("Better memory") == 1


def test_assign_primary_global_cap_prevents_type_collapse():
    """8 startups all prefer Better memory → at most ceil(8*0.25)=2 primaries."""
    fit_hi = PersonalFitRow(
        startup_id=1, technical_advantage=9, interest=9, existing_knowledge=9,
        sales_ability=9, long_term_moat=9, build_speed=9, market_size=9, distribution_fit=9,
    )
    fit_lo = PersonalFitRow(
        startup_id=1, technical_advantage=5, interest=5, existing_knowledge=5,
        sales_ability=5, long_term_moat=5, build_speed=5, market_size=5, distribution_fit=5,
    )
    candidates = []
    for i in range(8):
        fit = fit_hi if i < 2 else fit_lo
        fit = fit.model_copy(update={"startup_id": i + 1})
        wedges = [
            WedgeRow(id=i * 10 + 1, startup_id=i + 1, wedge_type="Better memory",
                     description="m", evidence="e", personal_fit_score=97),
            WedgeRow(id=i * 10 + 2, startup_id=i + 1, wedge_type="Open source",
                     description="o", evidence="e", personal_fit_score=80),
            WedgeRow(id=i * 10 + 3, startup_id=i + 1, wedge_type="Cheaper",
                     description="c", evidence="e", personal_fit_score=60),
        ]
        candidates.append((i + 1, wedges, fit))
    primaries = assign_primary_with_global_cap(candidates, cap_fraction=0.25)
    assert len(primaries) == 8
    mem = sum(1 for w in primaries.values() if w.wedge_type == "Better memory")
    # Soft cap ceil(8*0.25)=2; with only 3 types for 8 cos some overflow is
    # inevitable (balanced ceiling ≈ 3). Collapse (8/8) must not happen.
    assert mem <= 3
    assert mem < 8
    # highest-fit startups keep Better memory
    assert primaries[1].wedge_type == "Better memory"
    assert primaries[2].wedge_type == "Better memory"
    # majority diversify off Better memory
    other = [primaries[i].wedge_type for i in range(3, 9)]
    assert other.count("Better memory") <= 1
    assert set(other) & {"Open source", "Cheaper"}


def test_assign_primary_seeds_existing_counts_for_incremental_waves():
    """Incremental batch must respect full-cohort cap, not ceil(batch*0.25).

    Regression: force=False select of 5 new SIDs used n=5 → cap=2, so two
    more Better memory primaries landed every wave and the board collapsed.
    """
    fit = PersonalFitRow(
        startup_id=1, technical_advantage=8, interest=8, existing_knowledge=8,
        sales_ability=5, long_term_moat=7, build_speed=8, market_size=8, distribution_fit=6,
    )
    # Batch of 3 new startups, all prefer Better memory; cohort already has 50
    # Better memory primaries of 200 → cap ceil(200*0.25)=50 → zero new BM.
    candidates = []
    for i, sid in enumerate((201, 202, 203)):
        f = fit.model_copy(update={"startup_id": sid})
        wedges = [
            WedgeRow(id=i * 10 + 1, startup_id=sid, wedge_type="Better memory",
                     description="m", evidence="e", personal_fit_score=95),
            WedgeRow(id=i * 10 + 2, startup_id=sid, wedge_type="Developer-first",
                     description="d", evidence="e", personal_fit_score=90),
            WedgeRow(id=i * 10 + 3, startup_id=sid, wedge_type="AI-native",
                     description="a", evidence="e", personal_fit_score=85),
        ]
        candidates.append((sid, wedges, f))
    primaries = assign_primary_with_global_cap(
        candidates,
        cap_fraction=0.25,
        cohort_size=200,
        existing_primary_counts={"Better memory": 50},
    )
    assert len(primaries) == 3
    mem = sum(1 for w in primaries.values() if w.wedge_type == "Better memory")
    assert mem == 0, "batch must not open new Better memory slots when cohort cap full"
    assert all(w.wedge_type in {"Developer-first", "AI-native"} for w in primaries.values())


# --- gates: graduation ---


def test_graduation_gate_insufficient_sends():
    g = graduation_gate(sends=20, pain_signal_replies=2, replies=1)
    assert g.graduated is False
    assert "insufficient sends" in g.reason


def test_graduation_gate_low_reply_rate_flags_wedge_selection_not_outreach():
    g = graduation_gate(sends=30, pain_signal_replies=1, replies=1)
    assert g.graduated is False
    assert "wedge-selection is broken" in g.reason
    assert "not outreach copy" in g.reason


def test_graduation_gate_passes():
    g = graduation_gate(sends=40, pain_signal_replies=3, replies=3)
    assert g.graduated is True
    assert g.reply_rate == pytest.approx(0.075)


# --- gates: kill metric ---


def test_kill_metric_young_loop_no_trigger():
    now = datetime.now(timezone.utc)
    assert kill_metric_triggered(now - timedelta(days=1), now, 0) is False


def test_kill_metric_old_loop_no_pain_triggers():
    now = datetime.now(timezone.utc)
    assert kill_metric_triggered(now - timedelta(weeks=10), now, 0) is True


def test_kill_metric_old_loop_with_pain_does_not_trigger():
    now = datetime.now(timezone.utc)
    assert kill_metric_triggered(now - timedelta(weeks=10), now, 5) is False


# --- gates: promotion + edges ---


def test_promotion_gate_needs_cross_cluster():
    assert promotion_gate(3, ["developer"]) is False
    assert promotion_gate(3, ["developer", "infra"]) is True


def test_promotion_gate_needs_min_sightings():
    assert promotion_gate(2, ["developer", "infra"]) is False


def test_classify_edge_canonicalizes_or_rejects():
    assert classify_edge("solves") == "solves"
    assert classify_edge("related-to") is None
    assert ALLOWED_EDGE_TYPES == {
        "solves", "sub-problem-of", "suffers-from",
        "enables", "incumbent-of", "OSS-alternative-to",
    }


def test_should_retire_pattern_zero_growth_old():
    now = datetime.now(timezone.utc)
    assert should_retire_pattern(
        last_growth_rate=0,
        last_promoted_at=now - timedelta(days=45),
        now=now,
    ) is True


def test_should_retire_pattern_recent_promotion_kept():
    now = datetime.now(timezone.utc)
    assert should_retire_pattern(
        last_growth_rate=0,
        last_promoted_at=now - timedelta(days=5),
        now=now,
    ) is False


# --- gates: routing + builder precondition ---


def test_should_validate_skips_low_fit():
    low = PersonalFitRow(
        startup_id=1,
        technical_advantage=1, interest=1, existing_knowledge=1,
        sales_ability=1, long_term_moat=1, build_speed=1,
        market_size=1, distribution_fit=1,
    )
    assert should_validate(low) is False
    high = PersonalFitRow(
        startup_id=1,
        technical_advantage=10, interest=10, existing_knowledge=10,
        sales_ability=10, long_term_moat=10, build_speed=10,
        market_size=10, distribution_fit=10,
    )
    assert should_validate(high) is True


def test_route_after_validator_to_builder_on_graduate():
    r = ValidatorReceipt(
        result="done", stage="05", changed_rows=30, summary="ok",
        sends=40, replies=5, pain_signal_replies=4,
        reply_rate=0.125, graduated=True,
    )
    assert route_after_validator(r) == "06"


def test_route_after_validator_halts_on_kill_metric():
    r = ValidatorReceipt(
        result="done", stage="05", changed_rows=30, summary="ok",
        sends=40, replies=0, pain_signal_replies=0,
        reply_rate=0.0, graduated=False, kill_metric_triggered=True,
    )
    assert route_after_validator(r) is None  # halt


def test_builder_accepts_graduated_wedge_with_pain():
    ok, _ = builder_accepts(wedge_id=1, pain_reply_rows=3, startup_stage_marker="graduated")
    assert ok is True


def test_builder_rejects_un_graduated_wedge():
    ok, reason = builder_accepts(wedge_id=1, pain_reply_rows=3, startup_stage_marker="validated")
    assert ok is False
    assert "stage" in reason


def test_builder_rejects_insufficient_pain():
    ok, _ = builder_accepts(wedge_id=1, pain_reply_rows=1, startup_stage_marker="graduated")
    assert ok is False


# --- receipts ---


def test_parse_fenced_json_block():
    raw = """Here is the result:
```json
{"schema_version":"idea_factory_receipt_v1","result":"done","stage":"01","changed_rows":3,"summary":"ok","ingested":[1,2,3],"failed":[]}
```
Done."""
    r = parse(raw)
    assert isinstance(r, IngestorReceipt)
    assert r.ingested == [1, 2, 3]
    assert r.next_stage == "02"


def test_parse_fenced_nested_json_market_scout():
    """Nested arrays inside a fenced block must not truncate at the first `}`.

    The old non-greedy `\\{.*?\\}` fence regex broke MarketScout receipts
    (segments/candidates) and any Clusterer receipt with nested summary fields.
    """
    raw = (
        "Scout done.\n```json\n"
        '{"schema_version":"idea_factory_receipt_v1","result":"done","stage":"00",'
        '"changed_rows":2,"summary":"ok","markets_processed":1,"segments_created":1,'
        '"candidates_emitted":1,"segments":[{"parent_market":"AI Engineering",'
        '"segment_name":"IDE agents","icp_cluster":"developer","rationale":"r"}],'
        '"candidates":[{"name":"Cursor","website":"https://cursor.com",'
        '"market_segment_id":1,"yc_batch":"W24"}]}\n```\n'
    )
    r = parse(raw)
    assert isinstance(r, MarketScoutReceipt)
    assert r.candidates_emitted == 1
    assert r.segments[0].segment_name == "IDE agents"
    assert r.candidates[0].name == "Cursor"


def test_parse_bare_json_block():
    raw = '{"schema_version":"idea_factory_receipt_v1","result":"done","stage":"02","changed_rows":3,"summary":"ok","wedges_accepted":20,"wedges_rejected":0,"infra_ops_flagged_broader":1,"l5_shift_count":3}'
    r = parse(raw)
    assert isinstance(r, AnalystReceipt)
    assert r.wedges_accepted == 20


def test_parse_bare_json_with_prose_no_fence():
    # agents often emit `Here is the result: {...} done.`
    raw = ('Here is the result.\n'
           '{"schema_version":"idea_factory_receipt_v1","result":"done",'
           '"stage":"01","changed_rows":3,"summary":"ok",'
           '"ingested":[1,2,3],"failed":[]} thanks.')
    r = parse(raw)
    assert isinstance(r, IngestorReceipt)
    assert r.ingested == [1, 2, 3]


def test_parse_picks_receipt_block_over_earlier_unrelated_json():
    # a stray JSON snippet earlier in the message must not be mistaken for
    # the receipt; the balanced scan keys off the schema_version marker.
    raw = ('Stats so far: {"wedges": 9, "ops": 2}.\n'
           'receipt:{"schema_version":"idea_factory_receipt_v1","result":"done",'
           '"stage":"05","changed_rows":30,"summary":"ok","sends":30,"replies":4,'
           '"pain_signal_replies":4,"reply_rate":0.1333,"graduated":true,'
           '"kill_metric_triggered":false}')
    r = parse(raw)
    assert isinstance(r, ValidatorReceipt)
    assert r.graduated is True
    assert r.pain_signal_replies == 4


def test_parse_rejects_missing_schema_version():
    r = parse('{"result":"done","stage":"01","changed_rows":0,"summary":"x"}')
    assert hasattr(r, "reason")
    assert "schema_version" in r.reason


def test_parse_rejects_unknown_stage():
    r = parse('{"schema_version":"idea_factory_receipt_v1","result":"done","stage":"99","changed_rows":0,"summary":"x"}')
    assert hasattr(r, "reason")
    assert "99" in r.reason


def test_parse_rejects_corrupt_json():
    r = parse("not json at all")
    assert hasattr(r, "reason")


# --- end-to-end: one cohort flowing through the DAG ---


def test_end_to_end_cohort_flow(db, monkeypatch):
    """One startup goes from scout fan-out through to graduation.

    This is the 80/20 scenario. It walks the DAG starting from a market,
    through scout fan-out into candidate startups, through SID ingest,
    wedge ideation + evidence gate, scoring + human lock, validation,
    graduation, and finally the clusterer's promotion gate + Problem
    Graph edge enforcement. Anything outside the gates (recursion L1-L10,
    wedge copywriting, outreach copy) is reasoning, not code, and is
    not asserted here.
    """
    from idea_factory.pm import mark_runtime_started, get_runtime_started_at

    # 00 market scout: PM hands an Input; scout returns segments + candidates.
    # We simulate the scout's work by writing rows directly through the db
    # methods it would call.
    seg_id = db.upsert_market_segment(MarketSegmentRow(
        parent_market="Agent Infrastructure", segment_name="Agent memory",
        icp_cluster="infra", rationale="persistent context across runs",
    ))
    db.insert_candidate_startup(CandidateStartupRow(
        name="Letta", website="https://letta.com",
        market_segment_id=seg_id, yc_batch="W24", notes="MemGPT lineage",
    ))
    mark_runtime_started(db)
    assert get_runtime_started_at(db) is not None

    # PM fans out on the candidate list -> ingestor picks the one real candidate
    cands = db.candidates_for_ingest()
    assert len(cands) == 1
    assert cands[0].name == "Letta"

    # 01 ingestor: PM UPSERTs a startup + SID sections per candidate
    sid = db.upsert_startup(StartupRow(
        startup="Letta", website="https://letta.com", yc_batch="W24",
    ))
    db.upsert_competitive(CompetitiveRow(startup_id=sid, moat="weak OSS gap", weaknesses="no SOC 2"))
    db.set_stage_marker(sid, "ingested")
    assert db.get_startup(sid).stage_marker == "ingested"

    # 02 analyst: emits 3 representative wedges. Two have evidence, one None.
    wedges = [
        WedgeRow(startup_id=sid, wedge_type="Open source", description="OSS-first variant", evidence="competitive.moat=weak OSS gap"),
        WedgeRow(startup_id=sid, wedge_type="Self-hosted", description="on-prem", evidence="competitive.weaknesses=no SOC 2"),
        WedgeRow(startup_id=sid, wedge_type="Cheaper", description="half price", evidence=None),  # will be rejected
    ]
    db.replace_wedges(sid, wedges)
    db.set_stage_marker(sid, "analysed")

    # Gate: evidence drops the Cheaper wedge
    stored = db.get_wedges(sid)
    eg = evidence_gate(stored)
    assert len(eg.accepted) == 2
    assert all(w.evidence for w in eg.accepted)

    # 04 scorer: write a high fit, then lock (simulate user review)
    db.upsert_personal_fit(PersonalFitRow(
        startup_id=sid,
        technical_advantage=10, interest=10, existing_knowledge=10,
        sales_ability=10, long_term_moat=10, build_speed=10,
        market_size=10, distribution_fit=10,
    ))
    db.lock_personal_fit(sid, "archit")  # human-locked; agents cannot overwrite
    db.set_stage_marker(sid, "scored")
    fit = db.get_personal_fit(sid)
    assert should_validate(fit) is True

    # Gate: top wedge selection
    top = top_wedge(db.get_wedges(sid), fit)
    assert top is not None
    assert top.wedge_type in ("Open source", "Self-hosted")
    db.mark_wedge_selected(top.id, True)

    # 05 validator: simulate 40 sends with 4 pain-signal replies
    for i in range(40):
        db.insert_outreach_send(OutreachLogRow(
            wedge_id=top.id, startup_id=sid, message_id=f"msg-{i}",
            prospect_persona="AI infra eng lead",
        ))
    for i in range(4):
        db.mark_outreach_reply(i + 1, pain_signal=True)

    rows = db.outreach_for_wedge(top.id)
    sends = len(rows)
    pain_replies = sum(1 for r in rows if r.reply_pain_signal)
    replies = sum(1 for r in rows if r.replied_at)

    g = graduation_gate(sends=sends, pain_signal_replies=pain_replies, replies=replies)
    assert g.graduated is True
    db.set_stage_marker(sid, "graduated")

    # Gate: builder precondition
    ok, _ = builder_accepts(top.id, pain_replies, db.get_startup(sid).stage_marker)
    assert ok is True

    # 07 clusterer: pretend this wedge's problem appears across 2 of 3 clusters
    # (matches the segment the scout emitted with icp_cluster='infra'; we
    # add a 'developer' sighting to make the cross-cluster count work)
    assert promotion_gate(sightings=3, clusters_seen=["developer", "infra"]) is True
    pn_id = db.upsert_problem_node(ProblemNodeRow(canonical_name="AI memory", aliases=["context retention"]))
    edge_added = db.insert_problem_edge(ProblemEdgeRow(
        from_node=top.id, to_node=pn_id, edge_type="solves", source_ref=f"startup:{sid}",
    ))
    assert edge_added is True
    # free-form edge is rejected by the gate before any insert_problem_edge call
    assert classify_edge("related-to") is None

    # kill metric: scenario is young, plenty of pain replies, must not trigger
    now = datetime.now(timezone.utc)
    assert kill_metric_triggered(now, now, pain_replies) is False


# --- meta-loop: Infrastructure Graph + convergence gate ---


def test_infra_convergence_threshold_uses_ceil():
    assert infra_convergence_threshold(5, 0.5) == 3   # ceil(2.5)
    assert infra_convergence_threshold(4, 0.5) == 2
    assert infra_convergence_threshold(20, 0.5) == 10


def test_infra_convergence_gate_fires_at_half():
    g = infra_convergence_gate(sightings=3, cohort_size=5, distinct_clusters=2)
    assert g.converged is True
    assert g.threshold == 3
    assert g.distinct_clusters == 2


def test_infra_convergence_gate_does_not_fire_below_half():
    g = infra_convergence_gate(sightings=2, cohort_size=5, distinct_clusters=1)
    assert g.converged is False


def test_infra_convergence_gate_under_two_startups_never_converges():
    # no meta-signal from < 2 sightings, even at full coverage
    assert infra_convergence_gate(sightings=1, cohort_size=1).converged is False


def test_classify_infra_edge_canonicalizes_or_rejects():
    assert classify_infra_edge("needs") == "needs"
    assert classify_infra_edge("wants") is None
    assert classify_infra_edge("builds") == "builds"


def test_db_infrastructure_node_idempotent(db):
    nid = db.upsert_infrastructure_node(InfrastructureNodeRow(
        canonical_name="Memory layer", internal_platform="Memory",
        aliases=["Memory"], sightings=3, clusters_seen=["developer", "infra"],
        convergence=True, mini_spec="shared agent memory",
    ))
    nid2 = db.upsert_infrastructure_node(InfrastructureNodeRow(
        canonical_name="Memory layer", internal_platform="Memory",
        aliases=["Memory"], sightings=4, clusters_seen=["developer"],
        convergence=False, mini_spec="v2",
    ))
    assert nid == nid2
    rows = dict(db.infrastructure_nodes())
    node = rows[nid]
    assert node.sightings == 4
    assert node.mini_spec == "v2"
    # COALESCE keeps platform when re-upsert omits it
    assert node.internal_platform == "Memory"


def test_db_infrastructure_edge_idempotent(db):
    sid = db.upsert_startup(StartupRow(startup="A", website="https://a.example"))
    nid = db.upsert_infrastructure_node(InfrastructureNodeRow(
        canonical_name="Eval layer", internal_platform="Evaluation",
        aliases=["Evaluation"], sightings=1,
    ))
    edge = InfrastructureEdgeRow(
        startup_id=sid, infra_node_id=nid, edge_type="needs",
        source_ref="infra_ops:Evaluation",
    )
    assert db.insert_infrastructure_edge(edge) is True
    assert db.insert_infrastructure_edge(edge) is False  # idempotent
    sig = db.infrastructure_node_sightings(nid)
    assert sig == [(sid, "A")]


def test_pm_run_infra_convergence_builds_graph_and_flags_convergent(db):
    # 3 analysed startups across two ICP clusters, all flagged broader
    # applicability on Memory -> 'needs' edges -> Memory layer converges.
    from idea_factory.pm import run_infra_convergence
    from idea_factory.schema import InfrastructureOpRow

    seg_dev = db.upsert_market_segment(MarketSegmentRow(
        parent_market="Agent Infrastructure", segment_name="agent memory",
        icp_cluster="developer", rationale="x",
    ))
    seg_inf = db.upsert_market_segment(MarketSegmentRow(
        parent_market="AI Infrastructure", segment_name="infra",
        icp_cluster="infra", rationale="y",
    ))
    cohort_inputs = [
        ("MemOnly", seg_dev, "Cost optimization"),
        ("MemShared", seg_inf, "Tracing/observability"),
        ("Other", seg_dev, "Tracing/observability"),
    ]
    for name, seg_i, second_platform in cohort_inputs:
        website = f"https://{name.lower()}.example"
        sid = db.upsert_startup(StartupRow(startup=name, website=website))
        db.insert_candidate_startup(CandidateStartupRow(
            name=name, website=website, market_segment_id=seg_i,
        ))
        db.replace_infrastructure_ops(sid, [
            InfrastructureOpRow(
                startup_id=sid, internal_platform="Memory",
                description="every agent rewrites this internally",
                broader_applicability=1, evidence="competitive.moat=NULL",
            ),
            InfrastructureOpRow(
                startup_id=sid, internal_platform=second_platform,
                description="cost logging", broader_applicability=1,
                evidence="gpt-4 spend",
            ),
        ])
        db.set_stage_marker(sid, "analysed")

    cohort = db.count_analysed_startups()
    assert cohort == 3
    digest = run_infra_convergence(db, fraction=0.5)
    # threshold for a 3-cohort is 2; Memory sighted on 3/3 -> converges
    mem = next(d for d in digest if d["platform"] == "Memory")
    assert mem["sightings"] == 3
    assert mem["convergence"] is True
    assert mem["cohort"] == 3
    assert set(mem["clusters"]) == {"developer", "infra"}  # cross-cluster
    # nodes table reflects the same convergence flag
    rows = dict(db.infrastructure_nodes())
    mem_node = next(v for k, v in rows.items() if v.canonical_name == "Memory layer")
    assert mem_node.convergence is True
    assert mem_node.sightings == 3


def test_parse_market_scout_receipt_with_segments_and_candidates():
    # full scout receipt round-trip exercises the MarketScoutReceipt union member
    raw = (
        '{"schema_version":"idea_factory_receipt_v1","result":"done","stage":"00",'
        '"changed_rows":2,"summary":"ok","markets_processed":1,"segments_created":1,'
        '"candidates_emitted":1,"segments":[{"parent_market":"AI Engineering",'
        '"segment_name":"IDE agents","icp_cluster":"developer","rationale":"r"}],'
        '"candidates":[{"name":"Cursor","website":"https://cursor.com",'
        '"market_segment_id":1,"yc_batch":"W24"}]}'
    )
    r = parse(raw)
    assert isinstance(r, MarketScoutReceipt)
    assert r.candidates_emitted == 1
    assert r.segments[0].segment_name == "IDE agents"
    assert r.candidates[0].name == "Cursor"
    assert r.next_stage == "01"


# --- coverage gap fillers: builders + lightweight db methods + gates ---


def test_html_to_summary_strips_tags_and_truncates():
    from idea_factory.pm import html_to_summary
    s = html_to_summary("<html><body><p>Hello   <b>World</b></p></body></html>", max_chars=200)
    assert "Hello" in s and "World" in s and "<" not in s
    big = "<p>" + ("x " * 1000) + "</p>"
    out = html_to_summary(big, max_chars=1200)
    assert len(out) <= 1200 + len(" ...[truncated]")


def test_build_builder_input_round_trips(db):
    from idea_factory.pm import build_builder_input
    sid = db.upsert_startup(StartupRow(startup="A", website="https://a.example"))
    db.replace_wedges(sid, [
        WedgeRow(startup_id=sid, wedge_type="Open source", description="d", evidence="c"),
    ])
    wedge = db.get_wedges(sid)[0]
    # BuilderInput.pain_replies is min_length=3 — matches the builder_accepts
    # preconditions (>= 3 pain-signal replies). Seed exactly that many so
    # the builder can be handed a contract-shaped input.
    for i in range(3):
        oid = db.insert_outreach_send(OutreachLogRow(
            wedge_id=wedge.id, startup_id=sid, message_id=f"m-{i}",
            prospect_persona="eng lead",
        ))
        db.mark_outreach_reply(oid, pain_signal=True)
    inp = build_builder_input(db, sid, wedge.id)
    assert isinstance(inp, BuilderInput)
    assert inp.startup_id == sid
    assert inp.wedge.id == wedge.id
    assert inp.sid.startup == "A"
    assert len(inp.pain_replies) == 3
    # build_builder_input raises ValueError before any outreach lands
    sid2 = db.upsert_startup(StartupRow(startup="B", website="https://b.example"))
    db.replace_wedges(sid2, [WedgeRow(startup_id=sid2, wedge_type="Cheaper",
                                     description="d", evidence="c")])
    w2 = db.get_wedges(sid2)[0]
    with pytest.raises(Exception):
        build_builder_input(db, sid2, w2.id)


def test_mark_wedge_selected_round_trips(db):
    sid = db.upsert_startup(StartupRow(startup="A", website="https://a.example"))
    db.replace_wedges(sid, [
        WedgeRow(startup_id=sid, wedge_type="Open source", description="d", evidence="c"),
        WedgeRow(startup_id=sid, wedge_type="Cheaper", description="d2", evidence="c"),
    ])
    ws = db.get_wedges(sid)
    assert ws[0].selected is False
    db.mark_wedge_selected(ws[0].id, True, rank=1)
    db.mark_wedge_selected(ws[1].id, True, rank=2)
    # bool view: both selected
    assert all(w.selected for w in db.get_wedges(sid))
    # rank 1 is primary
    assert db.get_primary_wedge_id(sid) == ws[0].id
    raw = db._conn.execute(
        "SELECT id, selected FROM wedges WHERE startup_id=? ORDER BY id", (sid,)
    ).fetchall()
    by_id = {r["id"]: r["selected"] for r in raw}
    assert by_id[ws[0].id] == 1
    assert by_id[ws[1].id] == 2


def test_upsert_pattern_idempotent_on_canonical_name(db):
    row = PatternLibraryRow(
        canonical_name="Agent memory", aliases=["context retention"],
        sightings=3, mini_spec="shared agent memory layer",
    )
    db.upsert_pattern(row)
    row.sightings = 5
    db.upsert_pattern(row)  # idempotent on canonical_name; sightings update
    # no easy read-back helper; assert via raw select
    r = db._conn.execute(
        "SELECT sightings, mini_spec FROM pattern_library WHERE canonical_name = ?",
        ("Agent memory",),
    ).fetchone()
    assert r["sightings"] == 5
    assert r["mini_spec"] == "shared agent memory layer"


def test_insert_waitlist_round_trips(db):
    sid = db.upsert_startup(StartupRow(startup="A", website="https://a.example"))
    db.replace_wedges(sid, [
        WedgeRow(startup_id=sid, wedge_type="Open source", description="d", evidence="c"),
    ])
    w = db.get_wedges(sid)[0]
    wid = db.insert_waitlist(WaitlistRow(wedge_id=w.id, source="landing", referrer="x"))
    assert wid > 0


def test_promotion_gate_uses_controlled_icp_vocab(db):
    # promotion_gate validates clusters against ICP_CLUSTERS via
    # get_args(); a bogus cluster name does not count toward MIN_CLUSTERS.
    from idea_factory.decisions import VALID_ICP_CLUSTERS, promotion_gate
    assert VALID_ICP_CLUSTERS == {"developer", "infra", "enterprise-IT"}
    # 3 sightings covering 2 valid clusters -> True
    assert promotion_gate(3, ["developer", "infra"]) is True
    # a bogus cluster doesn't count even at 3 sightings
    assert promotion_gate(3, ["developer", "bogus"]) is False


# --- meta-loop: infra-node founder-fit scoring (v2 target) ---


def test_infra_node_fit_total_auto_computes():
    f = InfraNodeFitRow(
        infra_node_id=1,
        technical_advantage=10, interest=10, existing_knowledge=2,
        sales_ability=8, long_term_moat=10, build_speed=10,
        market_size=2, distribution_fit=8,
    )
    assert f.total == 60
    # shape matters: same total but wildly different profile
    f2 = InfraNodeFitRow(
        infra_node_id=1,
        technical_advantage=1, interest=1, existing_knowledge=1,
        sales_ability=1, long_term_moat=1, build_speed=1,
        market_size=1, distribution_fit=1,
    )
    assert f2.total == 8


def test_db_infra_personal_fit_human_lock(db):
    nid = db.upsert_infrastructure_node(InfrastructureNodeRow(
        canonical_name="Memory layer", internal_platform="Memory",
        sightings=4, clusters_seen=["developer", "infra"], convergence=True,
    ))
    wrote = db.upsert_infra_personal_fit(InfraNodeFitRow(
        infra_node_id=nid, technical_advantage=9, interest=10, existing_knowledge=10,
        sales_ability=5, long_term_moat=9, build_speed=8,
        market_size=8, distribution_fit=7,
    ))
    assert wrote is True
    db.lock_infra_personal_fit(nid, "archit")
    # human-locked; agents cannot overwrite
    wrote2 = db.upsert_infra_personal_fit(InfraNodeFitRow(
        infra_node_id=nid, technical_advantage=1, interest=1, existing_knowledge=1,
        sales_ability=1, long_term_moat=1, build_speed=1,
        market_size=1, distribution_fit=1,
    ))
    assert wrote2 is False
    fit = db.get_infra_personal_fit(nid)
    assert fit is not None
    assert fit.total == 66  # not overwritten
    assert fit.reviewed_by == "archit"


def test_db_convergent_infra_nodes_filters_on_flag(db):
    conv_id = db.upsert_infrastructure_node(InfrastructureNodeRow(
        canonical_name="Memory layer", internal_platform="Memory",
        sightings=4, convergence=True,
    ))
    nonconv_id = db.upsert_infrastructure_node(InfrastructureNodeRow(
        canonical_name="Scheduling layer", internal_platform="Scheduling",
        sightings=2, convergence=False,
    ))
    conv = dict(db.convergent_infra_nodes())
    assert conv_id in conv and nonconv_id not in conv
    assert conv[conv_id].canonical_name == "Memory layer"


def test_db_startups_backing_infra_node(db):
    sid = db.upsert_startup(StartupRow(startup="A", website="https://a.example"))
    nid = db.upsert_infrastructure_node(InfrastructureNodeRow(
        canonical_name="Eval layer", internal_platform="Evaluation",
        sightings=1, convergence=True,
    ))
    db.insert_infrastructure_edge(InfrastructureEdgeRow(
        startup_id=sid, infra_node_id=nid, edge_type="needs",
        source_ref="infra_ops:Evaluation",
    ))
    backing = db.startups_backing_infra_node(nid)
    assert [(s.id, s.startup) for s in backing] == [(sid, "A")]


def test_rank_infra_nodes_weights_conviction_over_fit():
    from idea_factory.decisions import rank_infra_nodes_by_fit, top_infra_node
    # Node A: 8/8 sightings, 3 clusters, moderate fit (0.7*80=56)
    a_fit = InfraNodeFitRow(
        infra_node_id=1, technical_advantage=7, interest=7, existing_knowledge=7,
        sales_ability=7, long_term_moat=7, build_speed=7, market_size=7, distribution_fit=7,
    )
    # Node B: 4/8 sightings, 1 cluster, perfect fit (1.0*80=80)
    b_fit = InfraNodeFitRow(
        infra_node_id=2, technical_advantage=10, interest=10, existing_knowledge=10,
        sales_ability=10, long_term_moat=10, build_speed=10, market_size=10, distribution_fit=10,
    )
    ranked = rank_infra_nodes_by_fit(
        scored=[(1, "Memory layer", a_fit), (2, "Scheduling layer", b_fit)],
        sightings={1: 8, 2: 4}, clusters={1: 3, 2: 1}, cohort_size=8,
    )
    # A wins: 0.5*0.7 + 0.3*1.0 + 0.2*1.0 = 0.85 vs B: 0.5*1.0 + 0.3*0.5 + 0.2*0.33 = 0.716
    assert ranked[0][0][0] == 1
    assert top_infra_node([(1, "Memory layer", a_fit), (2, "Scheduling layer", b_fit)],
                          {1: 8, 2: 4}, {1: 3, 2: 1}, 8) == (1, "Memory layer")


def test_top_infra_node_returns_none_when_nothing_scored():
    from idea_factory.decisions import top_infra_node
    assert top_infra_node([], {}, {}, 8) is None


def test_parse_infra_scorer_receipt_discriminates_on_stage_04():
    raw = ('{"schema_version":"idea_factory_receipt_v1","result":"done","stage":"04",'
           '"changed_rows":1,"summary":"Memory layer scored","infra_nodes_scored":1,'
           '"infra_nodes_skipped_human_locked":0,"top_infra_node":"Memory layer",'
           '"shape_outliers":[],"next_stage":"04"}')
    r = parse(raw)
    from idea_factory.schema import InfraScorerReceipt
    assert isinstance(r, InfraScorerReceipt)
    assert r.infra_nodes_scored == 1
    assert r.top_infra_node == "Memory layer"
    assert r.next_stage == "04"


def test_build_infra_node_scorer_input_round_trips(db):
    from idea_factory.pm import build_infra_node_scorer_input
    sid = db.upsert_startup(StartupRow(startup="A", website="https://a.example"))
    nid = db.upsert_infrastructure_node(InfrastructureNodeRow(
        canonical_name="Memory layer", internal_platform="Memory",
        sightings=1, clusters_seen=["developer"], convergence=True,
        mini_spec="shared agent memory",
    ))
    db.insert_infrastructure_edge(InfrastructureEdgeRow(
        startup_id=sid, infra_node_id=nid, edge_type="needs",
        source_ref="infra_ops:Memory",
    ))
    inp = build_infra_node_scorer_input(db, nid, founder_profile_path="skill/templates/founder-profile.md")
    assert isinstance(inp, InfraNodeScorerInput)
    assert inp.infra_node_id == nid
    assert inp.node.canonical_name == "Memory layer"
    assert len(inp.backing_startups) == 1
    assert inp.backing_startups[0].startup == "A"
    assert inp.founder_profile_path == "skill/templates/founder-profile.md"
    assert inp.existing_fit is None


def test_run_infra_fit_digest_ranks_and_picks_winner(db):
    from idea_factory.pm import run_infra_convergence, run_infra_fit_digest
    from idea_factory.schema import InfrastructureOpRow

    # 3 analysed startups all flagged broader on Memory (converges at 2/3)
    seg = db.upsert_market_segment(MarketSegmentRow(
        parent_market="Agent Infrastructure", segment_name="agent memory",
        icp_cluster="developer", rationale="x",
    ))
    from idea_factory.schema import CandidateStartupRow
    for i, name in enumerate(["A", "B", "C"]):
        website = f"https://{name.lower()}.example"
        sid = db.upsert_startup(StartupRow(startup=name, website=website))
        db.insert_candidate_startup(CandidateStartupRow(
            name=name, website=website, market_segment_id=seg,
        ))
        db.replace_infrastructure_ops(sid, [
            InfrastructureOpRow(
                startup_id=sid, internal_platform="Memory",
                description="rewrites", broader_applicability=1, evidence="e",
            ),
        ])
        db.set_stage_marker(sid, "analysed")

    run_infra_convergence(db, fraction=0.5)
    conv = db.convergent_infra_nodes()
    assert len(conv) >= 1
    memory_id = next(nid for nid, n in conv if n.canonical_name == "Memory layer")

    # score the convergent node like the scorer would
    db.upsert_infra_personal_fit(InfraNodeFitRow(
        infra_node_id=memory_id, technical_advantage=9, interest=10, existing_knowledge=10,
        sales_ability=6, long_term_moat=9, build_speed=8, market_size=8, distribution_fit=7,
    ))
    digest = run_infra_fit_digest(db, "skill/templates/founder-profile.md")
    assert digest["cohort"] == 3
    assert digest["scored_nodes"] >= 1
    assert digest["top_infra_node"] is not None
    assert digest["top_infra_node"]["canonical_name"] == "Memory layer"
    # enriched fields: PM needs fit_total + sightings without a second query
    assert digest["ranked"][0]["fit_total"] is not None
    assert digest["ranked"][0]["sightings"] >= 1
    assert digest["top_infra_node"]["fit_total"] is not None
    assert digest["top_infra_node"]["score"] is not None


def test_board_status_empty_db_surfaces_cold_start_blocker(db):
    from idea_factory.pm import board_status
    status = board_status(db)
    assert status["startups"] == 0
    assert status["analysed"] == 0
    assert any("empty board" in b for b in status["blockers"])


def test_board_status_after_cohort_lists_actionable_blockers(db):
    from idea_factory.pm import board_status, run_infra_convergence
    from idea_factory.schema import InfrastructureOpRow

    seg = db.upsert_market_segment(MarketSegmentRow(
        parent_market="Agent Infrastructure", segment_name="agent memory",
        icp_cluster="developer", rationale="x",
    ))
    for name in ["A", "B", "C"]:
        website = f"https://{name.lower()}.example"
        sid = db.upsert_startup(StartupRow(startup=name, website=website))
        db.insert_candidate_startup(CandidateStartupRow(
            name=name, website=website, market_segment_id=seg,
        ))
        db.replace_wedges(sid, [
            WedgeRow(startup_id=sid, wedge_type="Open source", description="d", evidence="c"),
        ])
        db.replace_infrastructure_ops(sid, [
            InfrastructureOpRow(
                startup_id=sid, internal_platform="Memory",
                description="rewrites", broader_applicability=1, evidence="e",
            ),
        ])
        db.upsert_personal_fit(PersonalFitRow(
            startup_id=sid, technical_advantage=8, interest=8, existing_knowledge=8,
            sales_ability=8, long_term_moat=8, build_speed=8,
            market_size=8, distribution_fit=8,
        ))
        db.set_stage_marker(sid, "scored")
    run_infra_convergence(db)

    status = board_status(db)
    assert status["startups"] == 3
    assert status["analysed"] == 3
    assert status["wedges"] == 3
    assert status["wedges_with_evidence"] == 3
    assert status["convergent_nodes"] >= 1
    assert status["by_stage"].get("scored") == 3
    # scored but no outreach; clusterer not ready; no infra fit scored; pre-build
    assert any("validator optional" in b or "no outreach" in b for b in status["blockers"])
    assert any("clusterer waiting" in b for b in status["blockers"])
    assert any("Mode B incomplete" in b for b in status["blockers"])
    assert any("builder disabled" in b for b in status["blockers"])
    assert status.get("prebuild_only") is True

# --- recursive fan-out planning ---


def test_canonical_markets_pool_size():
    # Pool expands past the original 20 with founder-relevant parents.
    assert len(CANONICAL_MARKETS) >= 20
    assert len(set(CANONICAL_MARKETS)) == len(CANONICAL_MARKETS)  # no dupes
    for required in (
        "AI Engineering", "Agent Memory", "Streaming Infrastructure",
        "AI Coding Agents", "Fraud Detection",
        "Agent Guardrails and Policy", "Computer Use Infrastructure", "Model Gateways",
        "Context Engineering", "Secrets and Credential Infrastructure", "AI Customer Support",
    ):
        assert required in CANONICAL_MARKETS


def test_uncovered_markets_and_scout_fanout(db):
    from idea_factory.pm import uncovered_markets, scout_fanout_inputs, market_coverage

    pool_n = len(CANONICAL_MARKETS)
    assert len(uncovered_markets(db)) == pool_n
    inputs = scout_fanout_inputs(db, markets_per_agent=2)
    assert len(inputs) == (pool_n + 1) // 2
    assert all(len(i.markets) <= 2 for i in inputs)
    # seed one market's segment → drops out of uncovered
    db.upsert_market_segment(MarketSegmentRow(
        parent_market="AI Engineering", segment_name="IDE agents",
        icp_cluster="developer", rationale="x",
    ))
    left = uncovered_markets(db)
    assert "AI Engineering" not in left
    assert len(left) == pool_n - 1
    cov = market_coverage(db)
    assert cov["pool_size"] == pool_n
    assert cov["with_segments"] == 1


def test_diversify_round_robin_prefers_undercovered():
    from idea_factory.pm import diversify_candidates_round_robin
    from idea_factory.schema import CandidateStartupRow

    pending = [
        (CandidateStartupRow(name="A1", website="https://a1.example", market_segment_id=1), "M1"),
        (CandidateStartupRow(name="A2", website="https://a2.example", market_segment_id=1), "M1"),
        (CandidateStartupRow(name="B1", website="https://b1.example", market_segment_id=2), "M2"),
        (CandidateStartupRow(name="C1", website="https://c1.example", market_segment_id=3), "M3"),
    ]
    picked = diversify_candidates_round_robin(
        pending, limit=3, prefer_markets=["M3", "M2"],
    )
    names = [c.name for c in picked]
    # prefer M3 then M2 then others — first picks should include C1 and B1
    assert names[0] == "C1"
    assert names[1] == "B1"
    assert names[2] == "A1"


def test_plan_recursive_fanout_priority_analyse_before_ingest(db):
    """Ingest-first drowned the board; analyse backlog always wins."""
    from idea_factory.pm import plan_recursive_fanout

    plan = plan_recursive_fanout(db, scout_markets_per_agent=5)
    assert plan["next_action"] == "scout"
    assert plan["prebuild_only"] is True
    assert "06" in plan["never_dispatch"]

    for i, m in enumerate(CANONICAL_MARKETS):
        seg = db.upsert_market_segment(MarketSegmentRow(
            parent_market=m, segment_name=f"seg-{i}",
            icp_cluster="developer", rationale="r",
        ))
        db.insert_candidate_startup(CandidateStartupRow(
            name=f"Co{i}", website=f"https://co{i}.example",
            market_segment_id=seg,
        ))
    sid = db.upsert_startup(StartupRow(startup="Backlog", website="https://backlog.example"))
    db.set_stage_marker(sid, "ingested")
    plan2 = plan_recursive_fanout(db, ingest_batch_size=5)
    assert plan2["next_action"] == "analyse"
    assert sid in plan2["wave"]["startup_ids"]
    assert plan2["queues"]["ingested_awaiting_analyse"] == 1


def test_plan_recursive_fanout_ingest_only_when_backlog_clear(db):
    from idea_factory.pm import plan_recursive_fanout

    for i, m in enumerate(CANONICAL_MARKETS):
        seg = db.upsert_market_segment(MarketSegmentRow(
            parent_market=m, segment_name=f"seg-{i}",
            icp_cluster="developer", rationale="r",
        ))
        db.insert_candidate_startup(CandidateStartupRow(
            name=f"Co{i}", website=f"https://co{i}.example",
            market_segment_id=seg,
        ))
    plan = plan_recursive_fanout(db, ingest_batch_size=5)
    assert plan["next_action"] == "ingest"
    assert plan["wave"]["parallel"] == 5


def test_plan_recursive_fanout_analyse_and_score_waves(db):
    from idea_factory.pm import plan_recursive_fanout

    for m in CANONICAL_MARKETS:
        db.upsert_market_segment(MarketSegmentRow(
            parent_market=m, segment_name=f"s-{m}",
            icp_cluster="infra", rationale="r",
        ))
    sid_ing = db.upsert_startup(StartupRow(startup="Ing", website="https://ing.example"))
    db.set_stage_marker(sid_ing, "ingested")
    plan = plan_recursive_fanout(db)
    assert plan["next_action"] == "analyse"
    assert sid_ing in plan["wave"]["startup_ids"]

    db.set_stage_marker(sid_ing, "analysed")
    db.replace_wedges(sid_ing, [
        WedgeRow(startup_id=sid_ing, wedge_type="Open source", description="d", evidence="c"),
    ])
    plan2 = plan_recursive_fanout(db)
    assert plan2["next_action"] == "score_a"
    assert sid_ing in plan2["wave"]["startup_ids"]


def test_run_select_top_wedges_marks_winner(db):
    from idea_factory.pm import run_select_top_wedges, plan_recursive_fanout

    sid = db.upsert_startup(StartupRow(startup="A", website="https://a.example"))
    db.set_stage_marker(sid, "analysed")
    db.replace_wedges(sid, [
        WedgeRow(startup_id=sid, wedge_type="Cheaper", description="low",
                 evidence="e1", personal_fit_score=40),
        WedgeRow(startup_id=sid, wedge_type="Open source", description="high",
                 evidence="e2", personal_fit_score=90),
        WedgeRow(startup_id=sid, wedge_type="Developer-first", description="mid",
                 evidence="e3", personal_fit_score=70),
    ])
    db.upsert_personal_fit(PersonalFitRow(
        startup_id=sid, technical_advantage=8, interest=8, existing_knowledge=8,
        sales_ability=8, long_term_moat=8, build_speed=8, market_size=8, distribution_fit=8,
    ))
    out = run_select_top_wedges(db)
    assert len(out) == 1
    assert out[0]["wedge_type"] == "Open source"
    selected = [w for w in db.get_wedges(sid) if w.selected]
    # multi-winner shortlist: up to 3 distinct types
    assert len(selected) == 3
    assert {w.wedge_type for w in selected} == {
        "Open source", "Developer-first", "Cheaper",
    }
    assert out[0]["shortlist_types"][0] == "Open source"
    plan = plan_recursive_fanout(db)
    assert sid not in plan["wave"].get("startup_ids", [])


def test_run_select_top_wedges_force_reselect_diversifies_cohort(db):
    from idea_factory.pm import run_select_top_wedges

    # 8 startups all scored Better memory highest — global cap must diversify
    for i in range(8):
        sid = db.upsert_startup(StartupRow(
            startup=f"Co{i}", website=f"https://co{i}.example",
        ))
        db.set_stage_marker(sid, "scored")
        db.replace_wedges(sid, [
            WedgeRow(startup_id=sid, wedge_type="Better memory", description="m",
                     evidence="e", personal_fit_score=97),
            WedgeRow(startup_id=sid, wedge_type="Open source", description="o",
                     evidence="e", personal_fit_score=80),
            WedgeRow(startup_id=sid, wedge_type="API-first", description="a",
                     evidence="e", personal_fit_score=70),
        ])
        # higher total for earlier ids so they keep Better memory
        t = 9 if i < 2 else 5
        db.upsert_personal_fit(PersonalFitRow(
            startup_id=sid,
            technical_advantage=t, interest=t, existing_knowledge=t,
            sales_ability=t, long_term_moat=t, build_speed=t,
            market_size=t, distribution_fit=t,
        ))
    out = run_select_top_wedges(db, force=True)
    assert len(out) == 8
    primaries = [r["wedge_type"] for r in out]
    assert primaries.count("Better memory") <= 3
    assert primaries.count("Better memory") < 8
    assert len(set(primaries)) >= 2
    # every startup still has a multi-type shortlist
    for r in out:
        assert len(r["shortlist"]) >= 2
        assert len(set(r["shortlist_types"])) == len(r["shortlist_types"])
