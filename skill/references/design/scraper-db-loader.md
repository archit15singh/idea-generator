# Scraper + DB Loader + DB Init (SQLite)

The persistence layer. The SID is one row per startup; the loader writes the analyses the agent produces. **Init is idempotent**, running it on an existing DB must be a no-op (CREATE TABLE IF NOT EXISTS), never destructive.

## Design rules

- **SQLite only, single file.** No server, no migrations framework, no ORM. Versioning is `PRAGMA user_version`.
- **Idempotent inserts.** Re-scraping a startup updates, it does not duplicate. Natural key = domain (`website`).
- **Separate scrape output from loader.** Scraper emits raw JSON to `scrapes/`; loader normalizes + writes DB. Keeps re-runs cheap and makes the generator (LLM fill) replayable.
- **Raw blob + structured columns.** Keep the full scraped HTML/JSON in a `raw` TEXT column; mirror the fields you actually query into typed columns. You query the typed columns, you debug the raw.

## Tables

```sql
PRAGMA foreign_keys = ON;

-- Core startup row (the SID "one row per startup")
CREATE TABLE IF NOT EXISTS startups (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  startup         TEXT NOT NULL,
  website         TEXT UNIQUE NOT NULL,           -- natural key
  yc_batch        TEXT,
  founders        TEXT,                            -- JSON array
  category        TEXT,
  funding         TEXT,
  open_source     INTEGER,                         -- 0/1/NULL
  pricing         TEXT,
  stage           TEXT,
  raw             TEXT,                            -- full scrape payload JSON
  source_url      TEXT,
  created_at      TEXT DEFAULT (datetime('now')),
  updated_at      TEXT DEFAULT (datetime('now')),
  user_version    INTEGER DEFAULT 0
);

-- Analysis sections (1 startup → 1 row each, normalized so each can be regenerated independently)
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

-- One-to-many: wedges (≥20 per startup) and infrastructure ops, scored individually
CREATE TABLE IF NOT EXISTS wedges (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  startup_id INTEGER NOT NULL REFERENCES startups(id) ON DELETE CASCADE,
  wedge_type TEXT NOT NULL,                        -- e.g. "Open source", "Compliance-first"
  description TEXT,
  personal_fit_score INTEGER,                      -- 0–100, see personalisation-and-founder-history.md
  selected INTEGER DEFAULT 0,                      -- 1 if chosen by selection stage
  created_at TEXT DEFAULT (datetime('now')),
  UNIQUE(startup_id, wedge_type, description)
);

CREATE TABLE IF NOT EXISTS infrastructure_ops (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  startup_id INTEGER NOT NULL REFERENCES startups(id) ON DELETE CASCADE,
  internal_platform TEXT NOT NULL,                 -- e.g. "Evaluation", "Memory"
  description TEXT,
  broader_applicability INTEGER,                  -- 0/1, flag for cross-market reuse
  created_at TEXT DEFAULT (datetime('now')),
  UNIQUE(startup_id, internal_platform)
);

-- Personal fit (one row per startup)
CREATE TABLE IF NOT EXISTS personal_fit (
  startup_id INTEGER PRIMARY KEY REFERENCES startups(id) ON DELETE CASCADE,
  technical_advantage INTEGER, interest INTEGER, existing_knowledge INTEGER,
  sales_ability INTEGER, long_term_moat INTEGER, build_speed INTEGER,
  market_size INTEGER, distribution_fit INTEGER,
  total INTEGER,                                  -- computed aggregate
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS scrape_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT NOT NULL,                           -- 'yc-directory' | 'startup-site' | 'github' | 'linkedin'
  target_url TEXT,
  status TEXT,                                    -- 'ok' | 'error' | 'partial'
  bytes INTEGER,
  error TEXT,
  ran_at TEXT DEFAULT (datetime('now'))
);

PRAGMA user_version = 1;
```

## Scraper (sources, in dependency order)

1. **YC directory**, `ycombinator.com/companies` (per-batch + per-category)." Seed list for the 20 markets.
2. **Startup website**, homepage, `/pricing`, `/docs`, `/about`, `/careers`.
3. **GitHub**, repo list, stars, license, last-commit, primary language.
4. **LinkedIn**, company size, industry, headcount trajectory (rate-limited / fragile; best-effort).

Each scraper:
- writes raw JSON to `scrapes/<domain>/<source>.json`,
- logs a `scrape_log` row,
- **never** writes analysis columns, only the loader does, and only after the generator runs.

## Loader contract

For each startup in the scrape queue:

1. `UPSERT` into `startups` keyed on `website`. Touch `updated_at`.
2. If new raw payload arrived, re-run the generator (see the OS docs) for the sections whose inputs changed.
3. `INSERT OR REPLACE` each analysis section row.
4. Child tables (`wedges`, `infrastructure_ops`) are **delete-then-insert** per startup per run (they are derived; stale is fine to discard).
5. Never mutate `personal_fit` automatically, that is a human-edited table (see `personal-fit-score.md`).

## Bootstrapping

```sh
sqlite3 sid.db < schema.sql        # idempotent, safe on existing DB
python load.py --source scrapes/  # idempotent upserts
```

Run order on a fresh checkout: `schema.sql` → scraper → loader → generator → analysis. Re-running any later stage must not require re-running earlier ones.