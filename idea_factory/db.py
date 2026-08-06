"""Typed SQLite layer for the idea-factory skill.

Idempotent upserts and typed reads for every DAG node's persistence.
Natural key for startups is `website`. Re-runs update, never duplicate.

Schema lives in `skill/templates/schema.sql` (the source of truth).
This module maps DB rows to the Pydantic types in `schema.py`.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

from idea_factory.schema import (
    AnalystInput,
    BuilderInput,
    ClustererInput,
    CompetitiveRow,
    CustomerRow,
    GTMRow,
    IngestorInput,
    InfrastructureOpRow,
    OutreachLogRow,
    PatternLibraryRow,
    PersonalFitRow,
    ProblemEdgeRow,
    ProblemNodeRow,
    ProblemRow,
    ProductRow,
    RecursivePathRow,
    ScorerInput,
    StartupRow,
    TechnicalRow,
    ValidatorInput,
    WaitlistRow,
    WedgeRow,
)

DEFAULT_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "skill" / "templates" / "schema.sql"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _json_dumps(v) -> Optional[str]:
    if v is None:
        return None
    return json.dumps(v) if not isinstance(v, str) else v


def _json_loads_list(v: Optional[str]) -> list:
    if not v:
        return []
    if isinstance(v, list):
        return v
    try:
        return json.loads(v)
    except json.JSONDecodeError:
        return []


class DB:
    """Connection wrapper. Every public method is a typed upsert or typed read."""

    def __init__(self, path: str, schema_path: Optional[Path] = None) -> None:
        self.path = path
        self.schema_path = schema_path or DEFAULT_SCHEMA_PATH
        self._conn: sqlite3.Connection = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")

    def init(self) -> None:
        """Idempotent schema creation. Safe on existing DB."""
        sql = self.schema_path.read_text()
        self._conn.executescript(sql)
        self._conn.commit()

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        cur = self._conn
        try:
            yield cur
            cur.commit()
        except Exception:
            cur.rollback()
            raise

    def close(self) -> None:
        self._conn.close()

    # --- startups + SID sections (ingestor node write; PM reads) ---

    def upsert_startup(self, row: StartupRow) -> int:
        """Idempotent on website. Returns startup_id."""
        with self.tx() as cur:
            cur.execute(
                """
                INSERT INTO startups
                  (startup, website, yc_batch, founders, category, funding,
                   open_source, pricing, stage, stage_marker, source_url, raw)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(website) DO UPDATE SET
                  startup=excluded.startup, yc_batch=excluded.yc_batch,
                  founders=excluded.founders, category=excluded.category,
                  funding=excluded.funding, open_source=excluded.open_source,
                  pricing=excluded.pricing, stage=excluded.stage,
                  stage_marker=excluded.stage_marker, source_url=excluded.source_url,
                  raw=excluded.raw,
                  updated_at=datetime('now')
                """,
                (
                    row.startup, row.website, row.yc_batch,
                    _json_dumps(row.founders), row.category, row.funding,
                    int(row.open_source) if row.open_source is not None else None,
                    row.pricing, row.stage, row.stage_marker, row.source_url, row.raw,
                ),
            )
            startup_id = cur.execute(
                "SELECT id FROM startups WHERE website = ?", (row.website,)
            ).fetchone()[0]
        return int(startup_id)

    def set_stage_marker(self, startup_id: int, marker: str) -> None:
        with self.tx() as cur:
            cur.execute(
                "UPDATE startups SET stage_marker = ?, updated_at = datetime('now') WHERE id = ?",
                (marker, startup_id),
            )

    def get_startup(self, startup_id: int) -> Optional[StartupRow]:
        r = self._conn.execute(
            "SELECT * FROM startups WHERE id = ?", (startup_id,)
        ).fetchone()
        if not r:
            return None
        return StartupRow(
            id=r["id"], startup=r["startup"], website=r["website"],
            yc_batch=r["yc_batch"], founders=_json_loads_list(r["founders"]),
            category=r["category"], funding=r["funding"],
            open_source=bool(r["open_source"]) if r["open_source"] is not None else None,
            pricing=r["pricing"], stage=r["stage"], stage_marker=r["stage_marker"],
            source_url=r["source_url"], raw=r["raw"],
        )

    def upsert_customer(self, row: CustomerRow) -> None:
        self._upsert_section("startup_customer", row)

    def upsert_problem(self, row: ProblemRow) -> None:
        self._upsert_section("startup_problem", row)

    def upsert_product(self, row: ProductRow) -> None:
        self._upsert_section("startup_product", row)

    def upsert_gtm(self, row: GTMRow) -> None:
        self._upsert_section("startup_gtm", row)

    def upsert_technical(self, row: TechnicalRow) -> None:
        self._upsert_section("startup_technical", row)

    def upsert_competitive(self, row: CompetitiveRow) -> None:
        self._upsert_section("startup_competitive", row)

    def _upsert_section(self, table: str, row) -> None:
        cols = [c for c in type(row).model_fields if c != "startup_id"]
        placeholders = ", ".join(["?"] * (len(cols) + 1))
        col_list = ", ".join(["startup_id"] + cols)
        update_cols = ", ".join([f"{c}=excluded.{c}" for c in cols])
        with self.tx() as cur:
            cur.execute(
                f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) "
                f"ON CONFLICT(startup_id) DO UPDATE SET {update_cols}, updated_at=datetime('now')",
                (row.startup_id, *[getattr(row, c) for c in cols]),
            )

    def get_sid_for_analyst(self, startup_id: int) -> AnalystInput:
        """Reads the full SID row + 6 sections, returns AnalystInput payload."""
        s = self.get_startup(startup_id)
        if s is None:
            raise KeyError(f"startup {startup_id} not found")
        return AnalystInput(
            startup_id=startup_id,
            sid=s,
            customer=self._get_one("startup_customer", startup_id, CustomerRow),
            problem=self._get_one("startup_problem", startup_id, ProblemRow),
            product=self._get_one("startup_product", startup_id, ProductRow),
            gtm=self._get_one("startup_gtm", startup_id, GTMRow),
            technical=self._get_one("startup_technical", startup_id, TechnicalRow),
            competitive=self._get_one("startup_competitive", startup_id, CompetitiveRow),
        )

    def _get_one(self, table: str, startup_id: int, cls):
        r = self._conn.execute(
            f"SELECT * FROM {table} WHERE startup_id = ?", (startup_id,)
        ).fetchone()
        if not r:
            return None
        return cls(**{k: r[k] for k in r.keys()})

    def startups_by_stage(self, marker: str) -> list[StartupRow]:
        rows = self._conn.execute(
            "SELECT * FROM startups WHERE stage_marker = ? ORDER BY id", (marker,)
        ).fetchall()
        return [
            StartupRow(
                id=r["id"], startup=r["startup"], website=r["website"],
                yc_batch=r["yc_batch"], founders=_json_loads_list(r["founders"]),
                category=r["category"], funding=r["funding"],
                open_source=bool(r["open_source"]) if r["open_source"] is not None else None,
                pricing=r["pricing"], stage=r["stage"], stage_marker=r["stage_marker"],
                source_url=r["source_url"], raw=r["raw"],
            )
            for r in rows
        ]

    # --- analyst node writes ---

    def upsert_recursive_path(self, row: RecursivePathRow) -> None:
        with self.tx() as cur:
            cur.execute(
                """
                INSERT INTO recursive_path
                  (startup_id, l1, l2, l3, l4, l5, l6, l7, l8, l9, l10, l5_shifts)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(startup_id) DO UPDATE SET
                  l1=excluded.l1, l2=excluded.l2, l3=excluded.l3, l4=excluded.l4,
                  l5=excluded.l5, l6=excluded.l6, l7=excluded.l7, l8=excluded.l8,
                  l9=excluded.l9, l10=excluded.l10, l5_shifts=excluded.l5_shifts,
                  updated_at=datetime('now')
                """,
                (row.startup_id, row.l1, row.l2, row.l3, row.l4, row.l5,
                 row.l6, row.l7, row.l8, row.l9, row.l10, _json_dumps(row.l5_shifts)),
            )

    def replace_wedges(self, startup_id: int, wedges: list[WedgeRow]) -> None:
        """Derived table: delete-then-insert per startup per regen. Stale is noise."""
        with self.tx() as cur:
            cur.execute("DELETE FROM wedges WHERE startup_id = ?", (startup_id,))
            for w in wedges:
                cur.execute(
                    """
                    INSERT INTO wedges
                      (startup_id, wedge_type, description, evidence, personal_fit_score, selected)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (startup_id, w.wedge_type, w.description, w.evidence,
                     w.personal_fit_score, int(w.selected)),
                )

    def replace_infrastructure_ops(
        self, startup_id: int, ops: list[InfrastructureOpRow]
    ) -> None:
        with self.tx() as cur:
            cur.execute("DELETE FROM infrastructure_ops WHERE startup_id = ?", (startup_id,))
            for op in ops:
                cur.execute(
                    """
                    INSERT INTO infrastructure_ops
                      (startup_id, internal_platform, description, broader_applicability, evidence)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (startup_id, op.internal_platform, op.description,
                     int(op.broader_applicability), op.evidence),
                )

    def get_wedges(self, startup_id: int) -> list[WedgeRow]:
        rows = self._conn.execute(
            "SELECT * FROM wedges WHERE startup_id = ? ORDER BY id", (startup_id,)
        ).fetchall()
        return [
            WedgeRow(
                id=r["id"], startup_id=r["startup_id"], wedge_type=r["wedge_type"],
                description=r["description"], evidence=r["evidence"],
                personal_fit_score=r["personal_fit_score"],
                selected=bool(r["selected"]),
                created_at=r["created_at"],
            )
            for r in rows
        ]

    # --- scorer node reads/writes ---

    def upsert_personal_fit(self, row: PersonalFitRow, force: bool = False) -> bool:
        """Returns False if a human-locked row exists and force=False (skip)."""
        existing = self._conn.execute(
            "SELECT reviewed_at FROM personal_fit WHERE startup_id = ?",
            (row.startup_id,),
        ).fetchone()
        if existing and existing["reviewed_at"] and not force:
            return False
        with self.tx() as cur:
            cur.execute(
                """
                INSERT INTO personal_fit
                  (startup_id, technical_advantage, interest, existing_knowledge,
                   sales_ability, long_term_moat, build_speed, market_size,
                   distribution_fit, total, reviewed_at, reviewed_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(startup_id) DO UPDATE SET
                  technical_advantage=excluded.technical_advantage,
                  interest=excluded.interest, existing_knowledge=excluded.existing_knowledge,
                  sales_ability=excluded.sales_ability, long_term_moat=excluded.long_term_moat,
                  build_speed=excluded.build_speed, market_size=excluded.market_size,
                  distribution_fit=excluded.distribution_fit, total=excluded.total,
                  updated_at=datetime('now')
                """,
                (row.startup_id, row.technical_advantage, row.interest,
                 row.existing_knowledge, row.sales_ability, row.long_term_moat,
                 row.build_speed, row.market_size, row.distribution_fit, row.total,
                 row.reviewed_at.isoformat() if row.reviewed_at else None,
                 row.reviewed_by),
            )
        return True

    def lock_personal_fit(self, startup_id: int, reviewed_by: str) -> None:
        """Human review gate. After this, agents cannot overwrite the row."""
        with self.tx() as cur:
            cur.execute(
                "UPDATE personal_fit SET reviewed_at = datetime('now'), reviewed_by = ? "
                "WHERE startup_id = ?",
                (reviewed_by, startup_id),
            )

    def get_personal_fit(self, startup_id: int) -> Optional[PersonalFitRow]:
        r = self._conn.execute(
            "SELECT * FROM personal_fit WHERE startup_id = ?", (startup_id,)
        ).fetchone()
        if not r:
            return None
        return PersonalFitRow(
            startup_id=r["startup_id"], technical_advantage=r["technical_advantage"],
            interest=r["interest"], existing_knowledge=r["existing_knowledge"],
            sales_ability=r["sales_ability"], long_term_moat=r["long_term_moat"],
            build_speed=r["build_speed"], market_size=r["market_size"],
            distribution_fit=r["distribution_fit"], total=r["total"],
            reviewed_at=r["reviewed_at"], reviewed_by=r["reviewed_by"],
        )

    def update_wedge_fit_score(
        self, startup_id: int, scores: dict[Optional[int], int]
    ) -> None:
        """scores maps wedge_id -> personal_fit_score (0-100)."""
        with self.tx() as cur:
            for wid, score in scores.items():
                if wid is None:
                    continue
                cur.execute(
                    "UPDATE wedges SET personal_fit_score = ? WHERE id = ?",
                    (score, wid),
                )

    def mark_wedge_selected(self, wedge_id: int, selected: bool = True) -> None:
        with self.tx() as cur:
            cur.execute(
                "UPDATE wedges SET selected = ? WHERE id = ?",
                (int(selected), wedge_id),
            )

    # --- validator node writes ---

    def insert_outreach_send(self, row: OutreachLogRow) -> int:
        with self.tx() as cur:
            cur.execute(
                """
                INSERT INTO outreach_log
                  (wedge_id, startup_id, message_id, sent_at, prospect_persona)
                VALUES (?, ?, ?, ?, ?)
                """,
                (row.wedge_id, row.startup_id, row.message_id, _now(), row.prospect_persona),
            )
            return int(cur.execute("SELECT last_insert_rowid()").fetchone()[0])

    def mark_outreach_reply(
        self, outreach_id: int, pain_signal: bool
    ) -> None:
        with self.tx() as cur:
            cur.execute(
                "UPDATE outreach_log SET replied_at = datetime('now'), reply_pain_signal = ? "
                "WHERE id = ?",
                (int(pain_signal), outreach_id),
            )

    def outreach_for_wedge(self, wedge_id: int) -> list[OutreachLogRow]:
        rows = self._conn.execute(
            "SELECT * FROM outreach_log WHERE wedge_id = ? ORDER BY id", (wedge_id,)
        ).fetchall()
        return [
            OutreachLogRow(
                id=r["id"], wedge_id=r["wedge_id"], startup_id=r["startup_id"],
                message_id=r["message_id"], sent_at=r["sent_at"],
                replied_at=r["replied_at"], reply_pain_signal=bool(r["reply_pain_signal"]),
                prospect_persona=r["prospect_persona"],
            )
            for r in rows
        ]

    # --- builder node writes ---

    def insert_waitlist(self, row: WaitlistRow) -> int:
        with self.tx() as cur:
            cur.execute(
                """
                INSERT INTO waitlist (wedge_id, source, referrer, icp_attributed, pricing_variant)
                VALUES (?, ?, ?, ?, ?)
                """,
                (row.wedge_id, row.source, row.referrer, row.icp_attributed, row.pricing_variant),
            )
            return int(cur.execute("SELECT last_insert_rowid()").fetchone()[0])

    # --- clusterer node writes ---

    def upsert_problem_node(self, row: ProblemNodeRow) -> int:
        with self.tx() as cur:
            cur.execute(
                """
                INSERT INTO problem_nodes (canonical_name, aliases)
                VALUES (?, ?)
                ON CONFLICT(canonical_name) DO UPDATE SET aliases=excluded.aliases
                """,
                (row.canonical_name, _json_dumps(row.aliases)),
            )
            return int(cur.execute(
                "SELECT id FROM problem_nodes WHERE canonical_name = ?", (row.canonical_name,)
            ).fetchone()[0])

    def insert_problem_edge(self, row: ProblemEdgeRow) -> bool:
        """Returns False if edge already exists (idempotent)."""
        with self.tx() as cur:
            cur.execute(
                """
                INSERT OR IGNORE INTO problem_edges
                  (from_node, to_node, edge_type, source_ref)
                VALUES (?, ?, ?, ?)
                """,
                (row.from_node, row.to_node, row.edge_type, row.source_ref),
            )
            return cur.total_changes > 0

    def upsert_pattern(self, row: PatternLibraryRow) -> None:
        with self.tx() as cur:
            cur.execute(
                """
                INSERT INTO pattern_library
                  (canonical_name, aliases, sightings, last_growth_rate,
                   last_promoted_at, retired_at, mini_spec)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(canonical_name) DO UPDATE SET
                  aliases=excluded.aliases, sightings=excluded.sightings,
                  last_growth_rate=excluded.last_growth_rate, mini_spec=excluded.mini_spec,
                  last_promoted_at=COALESCE(pattern_library.last_promoted_at, excluded.last_promoted_at),
                  updated_at=datetime('now')
                """,
                (row.canonical_name, _json_dumps(row.aliases), row.sightings,
                 row.last_growth_rate,
                 row.last_promoted_at.isoformat() if row.last_promoted_at else None,
                 row.retired_at.isoformat() if row.retired_at else None,
                 row.mini_spec),
            )

    def retire_pattern(self, pattern_id: int) -> None:
        with self.tx() as cur:
            cur.execute(
                "UPDATE pattern_library SET retired_at = datetime('now') WHERE id = ?",
                (pattern_id,),
            )

    def count_startups_since(self, since: Optional[datetime]) -> int:
        if since is None:
            return int(self._conn.execute("SELECT COUNT(*) FROM startups").fetchone()[0])
        return int(self._conn.execute(
            "SELECT COUNT(*) FROM startups WHERE updated_at > ?",
            (since.isoformat(timespec="seconds"),),
        ).fetchone()[0])