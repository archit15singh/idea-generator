# 01 / Ingest — scrape + extract + insert per startup

Run atomically per startup. Natural key = `website`. UPSERT semantics throughout. **Never invent** — null means "unknown", not "no".

## For each startup in the constrained pool (raw `personalisation-and-founder-history.md`)

### 1.1 Scrape

- `ycombinator.com/companies` — by batch + by category, filtered to the constrained market list.
- startup homepage, `/pricing`, `/docs`, `/about`, `/careers`.
- GitHub org — repo list, stars, license, primary language, last-commit.
- LinkedIn — best-effort; expected to fail often; log and move on.

Write raw JSON to `scrapes/<domain>/<source>.json`. Log every fetch in `scrape_log` (status ok/error/partial). Do **not** write analysis columns in 1.1.

### 1.2 Extract (the SID schema)

From the raw payloads, produce structured rows. UPSERT into `startups` keyed on `website`. Then write the six analysis tables (`INSERT OR REPLACE`; one row per startup per table):

- `startup_customer` — icp, company_size, buyer_persona, economic_buyer, user
- `startup_problem` — core_problem, existing_alternatives, why_current_fail, cost_of_not_solving
- `startup_product` — core_workflow, key_features, ai_capabilities, integrations
- `startup_gtm` — landing_page, positioning, pricing, sales_motion, plg_or_sales, distribution_channels
- `startup_technical` — likely_architecture, llms, memory, agents, vector_db, evaluation, observability
- `startup_competitive` — direct, indirect, oss_alternatives, moat, weaknesses

All empty → NULL. Never auto-fill. This stage produces no `recursive_path`, no `wedges`, no `infrastructure_ops` — those are later stages reading these rows.

### 1.3 Commit

One transaction per startup. Touch `startups.updated_at`. If raw payload changed since the last run, mark the startup for re-extraction in the next loop pass; downstream stages read this flag.

## Output

- one new/updated `startups` row with `raw` blob
- six analysis rows per startup
- `scrape_log` rows for every fetch

## Refs

- raw `scraper-db-loader.md` — the SQLite schema (idempotent; `CREATE TABLE IF NOT EXISTS`)
- raw `personalisation-and-founder-history.md` — the constrained market pool forming the seed list