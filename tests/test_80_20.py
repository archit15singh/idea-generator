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
    builder_accepts,
    classify_edge,
    evidence_gate,
    graduation_gate,
    kill_metric_triggered,
    promotion_gate,
    route_after_validator,
    should_retire_pattern,
    should_validate,
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
    IngestorInput,
    IngestorReceipt,
    MarketScoutInput,
    MarketScoutReceipt,
    MarketSegmentRow,
    OutreachLogRow,
    PersonalFitRow,
    ProblemEdgeRow,
    ProblemNodeRow,
    StartupRow,
    ValidatorReceipt,
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


def test_db_idempotent_upsert(db):
    s = StartupRow(startup="Acme", website="https://acme.example", yc_batch="W24")
    id1 = db.upsert_startup(s)
    id2 = db.upsert_startup(s)
    assert id1 == id2


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


def test_top_wedge_returns_none_when_all_lack_evidence():
    fit = PersonalFitRow(
        startup_id=1,
        technical_advantage=5, interest=5, existing_knowledge=5,
        sales_ability=5, long_term_moat=5, build_speed=5,
        market_size=5, distribution_fit=5,
    )
    ws = [WedgeRow(startup_id=1, wedge_type="Cheaper", description="d", evidence=None)]
    assert top_wedge(ws, fit) is None


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


def test_parse_bare_json_block():
    raw = '{"schema_version":"idea_factory_receipt_v1","result":"done","stage":"02","changed_rows":3,"summary":"ok","wedges_accepted":20,"wedges_rejected":0,"infra_ops_flagged_broader":1,"l5_shift_count":3}'
    r = parse(raw)
    assert isinstance(r, AnalystReceipt)
    assert r.wedges_accepted == 20


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