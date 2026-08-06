# 00 / Market scout (the DAG entry point)

The DAG starts from markets, never from a flat startup list. The market scout recursively breaks each market from the founder profile into sub-markets, classifies each to one of the 3 ICP clusters, and emits candidate YC startups per sub-market. The ingestor (node 01) then fans out on the scout's receipt.

## Why this stage exists

The reframe (see `references/design/personalisation-and-founder-history.md`): founder intuition is market-specific. The founder fills in a profile listing the markets where they have an unfair advantage, and the whole loop fans out from there. Without this node, the ingestor scrapes random startups and every downstream wedge inherits that randomness. With it, every wedge traces back to a market segment the chose deliberately.

## Controlled vocabularies (code, not your call)

- `parent_market` MUST be one of the canonical markets from `pm.CANONICAL_MARKETS`. Unknown parents are logged in `remaining_blockers` as "off-pool".
- `icp_cluster` is one of `developer`, `infra`, `enterprise-IT`. The classifier rejects free-form. This label is what the clusterer later counts for cross-cluster promotion.

## Do (per market)

1. Break the market down into sub-markets at the requested `depth`. The decomposition must be MECE within the market; collapse aliases.
2. Classify each segment to one `icp_cluster`. Pick the cluster where the economic buyer sits.
3. Emit 2-5 candidate YC startups per segment. Honest prior knowledge is fine; fabrication is a contract violation. If you cannot name 2 real candidates, surface in `remaining_blockers` rather than pad.
4. Commit: `db.upsert_market_segment` per segment, then `db.insert_candidate_startup` per candidate carrying the segment_id. Stamp `runtime_meta.started_at` via `pm.mark_runtime_started(db)` on the first successful pass — the kill metric counts from here.

## Output

- new rows in `market_segments` (one per sub-market)
- new rows in `candidate_startups` (2-5 per segment)
- a `MarketScoutReceipt` whose `candidates` field the PM fans out to the ingestor

## Refs

- agent prompt: `agents/idea-factory-market-scout.md`
- `references/design/personalisation-and-founder-history.md`: the canonical market pool
- `references/design/analysis.md`: why markets matter more than startup counts