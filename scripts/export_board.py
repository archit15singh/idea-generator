#!/usr/bin/env python3
"""Export sid.db → site/data/board.json for the Idea Board showcase."""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "sid.db"
OUT = ROOT / "site" / "data" / "board.json"


def decision_grade(w: dict | None) -> bool:
    if not w:
        return False
    d = (w.get("description") or "").strip()
    e = (w.get("evidence") or "").strip()
    if not d or d.startswith("MVP"):
        return False
    if not e or e == "thin" or len(e) < 15:
        return False
    return True


def export(db_path: Path = DB, out_path: Path = OUT) -> dict:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    startups = c.execute(
        """
        SELECT s.id, s.startup, s.website, s.yc_batch, s.founders, s.category, s.funding,
               s.open_source, s.pricing, s.stage, s.stage_marker, s.source_url, s.created_at,
               sc.icp, sc.company_size, sc.buyer_persona,
               sp.core_problem, sp.existing_alternatives, sp.why_current_fail, sp.cost_of_not_solving,
               pr.core_workflow, pr.key_features, pr.ai_capabilities, pr.integrations,
               g.positioning, g.pricing as gtm_pricing, g.sales_motion, g.plg_or_sales,
               t.likely_architecture, t.llms, t.memory, t.agents, t.vector_db, t.evaluation, t.observability,
               comp.direct_competitors, comp.indirect_competitors, comp.oss_alternatives, comp.moat, comp.weaknesses,
               pf.total as fit_total, pf.technical_advantage, pf.interest, pf.existing_knowledge,
               pf.sales_ability, pf.long_term_moat, pf.build_speed, pf.market_size, pf.distribution_fit
        FROM startups s
        LEFT JOIN startup_customer sc ON sc.startup_id=s.id
        LEFT JOIN startup_problem sp ON sp.startup_id=s.id
        LEFT JOIN startup_product pr ON pr.startup_id=s.id
        LEFT JOIN startup_gtm g ON g.startup_id=s.id
        LEFT JOIN startup_technical t ON t.startup_id=s.id
        LEFT JOIN startup_competitive comp ON comp.startup_id=s.id
        LEFT JOIN personal_fit pf ON pf.startup_id=s.id
        ORDER BY COALESCE(pf.total,0) DESC, s.id
        """
    ).fetchall()

    wedges = c.execute(
        """
        SELECT id, startup_id, wedge_type, description, evidence, personal_fit_score, selected, created_at
        FROM wedges ORDER BY startup_id, selected DESC, personal_fit_score DESC
        """
    ).fetchall()

    patterns = c.execute(
        """
        SELECT id, canonical_name, aliases, sightings, last_growth_rate, last_promoted_at, mini_spec
        FROM pattern_library ORDER BY sightings DESC
        """
    ).fetchall()

    infra = c.execute(
        """
        SELECT id, canonical_name, internal_platform, sightings, convergence, mini_spec
        FROM infrastructure_nodes ORDER BY sightings DESC
        """
    ).fetchall()

    markets = c.execute(
        """
        SELECT parent_market, COUNT(*) segs, GROUP_CONCAT(segment_name, ' · ') segs_list
        FROM market_segments GROUP BY parent_market ORDER BY parent_market
        """
    ).fetchall()

    wedges_by: dict[int, list] = {}
    for w in wedges:
        wedges_by.setdefault(w["startup_id"], []).append(dict(w))

    items = []
    for s in startups:
        d = dict(s)
        ws = wedges_by.get(s["id"], [])
        primary = next((w for w in ws if w["selected"] == 1), None)
        shortlist = [w for w in ws if w["selected"] >= 2]
        d["primary"] = primary
        d["shortlist"] = shortlist
        d["wedge_count"] = len(ws)
        d["decision_grade"] = decision_grade(primary)
        d["wedges"] = ws
        items.append(d)

    meta = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "startups": len(items),
        "wedges": len(wedges),
        "primaries": sum(1 for i in items if i["primary"]),
        "decision_grade_primaries": sum(1 for i in items if i["decision_grade"]),
        "patterns": len(patterns),
        "markets": len(markets),
        "infra_layers": len(infra),
        "avg_fit": round(sum((i["fit_total"] or 0) for i in items) / max(len(items), 1), 1),
        "open_source": sum(1 for i in items if i["open_source"]),
    }

    board = {
        "meta": meta,
        "startups": items,
        "patterns": [dict(p) for p in patterns],
        "infra": [dict(x) for x in infra],
        "markets": [dict(m) for m in markets],
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(board, ensure_ascii=False, separators=(",", ":")))
    conn.close()
    return meta


if __name__ == "__main__":
    meta = export()
    print(json.dumps(meta, indent=2))
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.2f} MB)", file=sys.stderr)
