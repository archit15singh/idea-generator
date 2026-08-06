-- sid.db — idempotent schema. Safe on existing DB.
-- Run: sqlite3 sid.db < schema.sql

PRAGMA foreign_keys = ON;
PRAGMA user_version = 1;

CREATE TABLE IF NOT EXISTS startups (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  startup         TEXT NOT NULL,
  website         TEXT UNIQUE NOT NULL,
  yc_batch        TEXT,
  founders        TEXT,
  category        TEXT,
  funding         TEXT,
  open_source     INTEGER,
  pricing         TEXT,
  stage           TEXT,
  stage_marker    TEXT,                          -- 'ingested' | 'analysed' | 'scored' | 'validated' | 'graduated' | 'built'
  raw             TEXT,
  source_url      TEXT,
  created_at      TEXT DEFAULT (datetime('now')),
  updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS startup_customer (
  startup_id INTEGER PRIMARY KEY REFERENCES startups(id) ON DELETE CASCADE,
  icp TEXT, company_size TEXT, buyer_persona TEXT, economic_buyer TEXT, user TEXT,
  updated_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS startup_problem (
  startup_id INTEGER PRIMARY KEY REFERENCES startups(id) ON DELETE CASCADE,
  core_problem TEXT, existing_alternatives TEXT, why_current_fail TEXT, cost_of_not_solving TEXT,
  updated_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS startup_product (
  startup_id INTEGER PRIMARY KEY REFERENCES startups(id) ON DELETE CASCADE,
  core_workflow TEXT, key_features TEXT, ai_capabilities TEXT, integrations TEXT,
  updated_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS startup_gtm (
  startup_id INTEGER PRIMARY KEY REFERENCES startups(id) ON DELETE CASCADE,
  landing_page TEXT, positioning TEXT, pricing TEXT, sales_motion TEXT,
  plg_or_sales TEXT, distribution_channels TEXT,
  updated_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS startup_technical (
  startup_id INTEGER PRIMARY KEY REFERENCES startups(id) ON DELETE CASCADE,
  likely_architecture TEXT, llms TEXT, memory TEXT, agents TEXT,
  vector_db TEXT, evaluation TEXT, observability TEXT,
  updated_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS startup_competitive (
  startup_id INTEGER PRIMARY KEY REFERENCES startups(id) ON DELETE CASCADE,
  direct_competitors TEXT, indirect_competitors TEXT, oss_alternatives TEXT,
  moat TEXT, weaknesses TEXT,
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS recursive_path (
  startup_id INTEGER PRIMARY KEY REFERENCES startups(id) ON DELETE CASCADE,
  l1 TEXT, l2 TEXT, l3 TEXT, l4 TEXT, l5 TEXT,
  l6 TEXT, l7 TEXT, l8 TEXT, l9 TEXT, l10 TEXT,
  l5_shifts TEXT,                                  -- JSON array; the wedge-generating level
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS wedges (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  startup_id INTEGER NOT NULL REFERENCES startups(id) ON DELETE CASCADE,
  wedge_type TEXT NOT NULL,
  description TEXT,
  evidence TEXT,                                   -- cite competitive/customer field; NULL → rejected
  personal_fit_score INTEGER,                      -- 0–100; set by scorer
  selected INTEGER DEFAULT 0,                      -- 0=no; 1=primary; 2+=shortlist rank
  created_at TEXT DEFAULT (datetime('now')),
  UNIQUE(startup_id, wedge_type, description)
);
CREATE INDEX IF NOT EXISTS wedges_startup_idx ON wedges(startup_id);
CREATE INDEX IF NOT EXISTS wedges_type_idx ON wedges(wedge_type);

CREATE TABLE IF NOT EXISTS infrastructure_ops (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  startup_id INTEGER NOT NULL REFERENCES startups(id) ON DELETE CASCADE,
  internal_platform TEXT NOT NULL,
  description TEXT,
  broader_applicability INTEGER,
  evidence TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  UNIQUE(startup_id, internal_platform)
);

CREATE TABLE IF NOT EXISTS personal_fit (
  startup_id INTEGER PRIMARY KEY REFERENCES startups(id) ON DELETE CASCADE,
  technical_advantage INTEGER, interest INTEGER, existing_knowledge INTEGER,
  sales_ability INTEGER, long_term_moat INTEGER, build_speed INTEGER,
  market_size INTEGER, distribution_fit INTEGER,
  total INTEGER,
  reviewed_at TEXT,                                -- non-NULL = human-locked; agents must not overwrite
  reviewed_by TEXT,
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS outreach_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  wedge_id INTEGER REFERENCES wedges(id) ON DELETE CASCADE,
  startup_id INTEGER REFERENCES startups(id) ON DELETE CASCADE,
  message_id TEXT,                                 -- gmail message ID
  sent_at TEXT DEFAULT (datetime('now')),
  replied_at TEXT,
  reply_pain_signal INTEGER DEFAULT 0,             -- 1 if reply indicates real pain (validator sets)
  prospect_persona TEXT
);
CREATE INDEX IF NOT EXISTS outreach_wedge_idx ON outreach_log(wedge_id);
CREATE INDEX IF NOT EXISTS outreach_reply_idx ON outreach_log(reply_pain_signal);

CREATE TABLE IF NOT EXISTS waitlist (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  wedge_id INTEGER REFERENCES wedges(id) ON DELETE CASCADE,
  source TEXT, referrer TEXT, icp_attributed TEXT,
  pricing_variant TEXT,
  signed_up_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS pattern_library (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  canonical_name TEXT UNIQUE NOT NULL,
  aliases TEXT,                                   -- JSON array; alias map
  sightings INTEGER DEFAULT 0,
  last_growth_rate INTEGER,                        -- sightings delta over last 30d
  last_promoted_at TEXT,
  retired_at TEXT,
  mini_spec TEXT,                                  -- incidental payers, OSS, weak incumbent
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS problem_nodes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  canonical_name TEXT UNIQUE NOT NULL,
  aliases TEXT,                                   -- controlled-vocab alias map
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS problem_nodes_name_idx ON problem_nodes(canonical_name);

CREATE TABLE IF NOT EXISTS problem_edges (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  from_node INTEGER REFERENCES problem_nodes(id) ON DELETE CASCADE,
  to_node INTEGER REFERENCES problem_nodes(id) ON DELETE CASCADE,
  edge_type TEXT NOT NULL,                        -- controlled vocab; see problem-graph.md
  source_ref TEXT,                                -- which startup_id or paper/node backs this edge
  created_at TEXT DEFAULT (datetime('now')),
  UNIQUE(from_node, to_node, edge_type, source_ref)
);
CREATE INDEX IF NOT EXISTS problem_edges_type_idx ON problem_edges(edge_type);

-- The Infrastructure Graph (parallel to the Problem Graph). The analyst emits
-- free-form infrastructure_ops rows per startup; the clusterer canonicalizes
-- them into infrastructure_nodes (one row per recurring internal platform,
-- e.g. "Universal Agent Memory") and links each startup to the nodes it
-- needs/builds/uses via infrastructure_edges. This is what powers the
-- meta-loop convergence question: "which infrastructure layer shows up across
-- >= half of these startups?". Without canonicalization the clusterer can
-- only count free-form descriptions, not sightings.
CREATE TABLE IF NOT EXISTS infrastructure_nodes (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  canonical_name  TEXT UNIQUE NOT NULL,
  internal_platform TEXT,                       -- the controlled INTERNAL_PLATFORMS slot
  aliases         TEXT,                          -- JSON array of alias names seen in infra ops rows
  sightings       INTEGER DEFAULT 0,            -- distinct startups sighted on
  clusters_seen   TEXT,                          -- JSON array of distinct ICP clusters
  convergence     INTEGER DEFAULT 0,             -- 1 when sightings >= half of analysed cohort
  mini_spec       TEXT,
  retired_at      TEXT,
  created_at      TEXT DEFAULT (datetime('now')),
  updated_at      TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS infrastructure_nodes_name_idx ON infrastructure_nodes(canonical_name);

CREATE TABLE IF NOT EXISTS infrastructure_edges (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  startup_id  INTEGER NOT NULL REFERENCES startups(id) ON DELETE CASCADE,
  infra_node_id INTEGER NOT NULL REFERENCES infrastructure_nodes(id) ON DELETE CASCADE,
  edge_type   TEXT NOT NULL,                     -- controlled vocab: 'needs' | 'builds' | 'uses' | 'has-gap'
  source_ref  TEXT,                              -- which infra ops row or wedge backs this edge
  created_at  TEXT DEFAULT (datetime('now')),
  UNIQUE(startup_id, infra_node_id, edge_type, source_ref)
);
CREATE INDEX IF NOT EXISTS infrastructure_edges_node_idx ON infrastructure_edges(infra_node_id);
CREATE INDEX IF NOT EXISTS infrastructure_edges_type_idx ON infrastructure_edges(edge_type);

CREATE TABLE IF NOT EXISTS infra_personal_fit (
  infra_node_id INTEGER PRIMARY KEY REFERENCES infrastructure_nodes(id) ON DELETE CASCADE,
  technical_advantage INTEGER, interest INTEGER, existing_knowledge INTEGER,
  sales_ability INTEGER, long_term_moat INTEGER, build_speed INTEGER,
  market_size INTEGER, distribution_fit INTEGER,
  total INTEGER,
  reviewed_at TEXT,                                -- non-NULL = human-locked; agents must not overwrite
  reviewed_by TEXT,
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS scrape_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT NOT NULL,
  target_url TEXT,
  status TEXT,
  bytes INTEGER,
  error TEXT,
  ran_at TEXT DEFAULT (datetime('now'))
);

-- Market scout outputs. The DAG starts from markets, not startups. The scout
-- recursively breaks markets into sub-markets (segments) and emits candidate
-- YC startups per segment. Ingestor fans out on the scout's receipt.
CREATE TABLE IF NOT EXISTS market_segments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  parent_market TEXT NOT NULL,
  segment_name TEXT NOT NULL,
  icp_cluster TEXT NOT NULL,                        -- 'developer' | 'infra' | 'enterprise-IT'
  rationale TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  UNIQUE(parent_market, segment_name)
);

CREATE TABLE IF NOT EXISTS candidate_startups (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  website TEXT UNIQUE NOT NULL,
  market_segment_id INTEGER REFERENCES market_segments(id) ON DELETE CASCADE,
  yc_batch TEXT,
  notes TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);

-- Kill-metric window + clusterer last-run timestamps (used by pm.py)
CREATE TABLE IF NOT EXISTS runtime_meta (
  key TEXT PRIMARY KEY,
  value TEXT,
  updated_at TEXT DEFAULT (datetime('now'))
);

-- Fixed edge vocabulary enforced at app level; mirror here for query ergonomics:
-- solves, sub-problem-of, suffers-from, enables, incumbent-of, OSS-alternative-to