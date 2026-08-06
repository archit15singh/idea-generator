# 01 / Ingest

Run atomically per startup. Natural key = `website`. UPSERT throughout. Never invent: NULL means unknown, not no.

## For each startup in the constrained pool (`references/design/personalisation-and-founder-history.md`)

### 1.1 Scrape

Fetch in this order. Record every fetch in `scrape_log`.

- `ycombinator.com/companies` for the company page (batch, founders, category, funding, stage)
- startup homepage, `/pricing`, `/docs`, `/about`, `/careers` (best-effort; accept 404s)
- GitHub org: repo list, stars, license, primary language, last-commit
- LinkedIn: best-effort, likely to fail; log and move on

Write raw JSON to `scrapes/<domain>/<source>.json` for each. Do not write analysis columns in 1.1.

### 1.2 Extract (the SID schema)

From the raw payloads, produce structured rows. The schema in `references/design/scraper-db-loader.md` is the contract.

- UPSERT `startups` keyed on `website`. Set `raw` to the aggregated JSON blob.
- `INSERT OR REPLACE` into the six analysis tables: `startup_customer`, `startup_problem`, `startup_product`, `startup_gtm`, `startup_technical`, `startup_competitive`.
- Set `startups.stage_marker = 'ingested'` on completion.

Empty fields are NULL. Do not auto-fill. This stage produces no `recursive_path`, no `wedges`, no `infrastructure_ops`. Those are later stages reading these rows.

### 1.3 Commit

One transaction per startup. Touch `startups.updated_at`. If raw payload changed since the last run, mark the startup for re-extraction; downstream stages read this flag.

## Output

- one new/updated `startups` row with `raw` blob
- six analysis rows per startup
- `scrape_log` rows for every fetch

## Refs

- `references/design/scraper-db-loader.md`: the SQLite schema (idempotent; `CREATE TABLE IF NOT EXISTS`)
- `references/design/personalisation-and-founder-history.md`: the constrained market pool forming the seed list