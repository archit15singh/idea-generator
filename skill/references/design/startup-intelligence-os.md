# Startup Intelligence OS

Don't hand-maintain the SID forever. Build a system that ingests and reasons. **But not yet**, see build sequence below.

## Capabilities

- **Auto-ingest** every new YC company (scraper, see `scraper-db-loader.md`).
- **Crawl** website, docs, pricing, GitHub, LinkedIn.
- **Generate** the full SID analysis automatically: customer profile, wedge opportunities, moat, GTM, OSS alternatives, infrastructure opportunities.
- **Cluster** by underlying problem, **not** category label, this is what makes patterns visible (`pattern-library.md`).

## Queryable intent

- "Show me every YC startup whose core dependency is persistent AI memory."
- "Find developer-tool startups with weak open-source competition."
- "Which three markets have the highest concentration of successful AI infra companies but the fewest OSS alternatives?"

These queries only become answerable at v2/v3, they need the Problem Graph's controlled vocabulary to resolve terms like "persistent AI memory" to a node ID.

## Build sequence (the load-bearing part)

| Phase | What | Why |
|-------|------|-----|
| v0 (now)      | Hand-curated markdown/SQLite, ~50 rows       | Validate the schema. Fields churn on contact with real startups. |
| v1 (after 50) | Generated analysis with human review; OSS-only ingestion | Crawler on `ycombinator.com/companies`, basic LLM fill, human-locked edits. |
| v2 (after 200)| Cluster-by-problem + query layer              | Only worth it once patterns are detectable. Earlier is premature. |
| v3            | Problem Graph (see `problem-graph.md`)        | The strategic moat. |

## The failure mode

Building v2 before v0 has ~50 rows of manually-shaped data. The schema will not survive contact with reality, and the generator will be trained on a moving target, every refactor invalidates prior LLM fills. The OS is a **consequence** of the data being good, not a substitute for hand-shaping it first.