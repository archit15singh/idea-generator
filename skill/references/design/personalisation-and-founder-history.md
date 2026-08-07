# Personalisation + Founder History

The original instinct, analyze 100 random YC startups, maximises for breadth. The reframe maximises for **founder intuition in markets where you have an unfair advantage**.

## Why constrain the search space

- Random sampling produces a catalog. Constrained sampling produces a **mental model** of where value concentrates.
- The goal is not "ideas generated", it is "intuition developed." Intuition is market-specific, not market-agnostic.
- Founder-market fit is the highest-value variable. Constraining to markets you already understand compounds your unfair advantages instead of fighting them.

## The canonical market pool (starts at 20; expands)

**Source of truth:** `idea_factory.pm.CANONICAL_MARKETS` (live length ≥20; expand with founder-relevant parents — do not freeze at 20). Scout fan-out and `market_coverage` read that list, not this table.

| Cluster | Markets |
|---------|---------|
| **developers/founders** | AI Engineering, Developer Tools, Agent Infrastructure, Technical Founder Tools, Developer Infrastructure, **AI Coding Agents**, **Agent Guardrails and Policy**, **Computer Use Infrastructure**, **Context Engineering** |
| **platform / infra** | Knowledge Management, AI Infrastructure, Observability, Data Infrastructure, MLOps and Evaluation, Vector Search and Retrieval, API and Integration Platforms, Workflow Orchestration, **Agent Memory**, **Streaming Infrastructure**, **Model Gateways**, **Secrets and Credential Infrastructure** |
| **enterprise / security** | Cybersecurity, Enterprise AI, Enterprise Automation, B2B Productivity, Email Security, Identity and Access, Security Automation, **Fraud Detection**, **AI Customer Support** |

**2026-08 expansion (founder profile):** Agent Memory (Memori/PyCon thesis), Streaming Infrastructure (Kafka day-job), AI Coding Agents (persistent coding-agent context), Fraud Detection (Abnormal entity-scoring / BEC-adjacent).

**2026-08 expand-27:** Agent Guardrails and Policy (hard-constraints-in-code / Luffy policy-engine thesis), Computer Use Infrastructure (Browserbase MCP fork, vision browser agents), Model Gateways (OpenRouter multi-provider / cost routing).

**2026-08 expand-30:** Context Engineering (prompt/memory/RAG composition for agents — Memori + agent-loop home turf), Secrets and Credential Infrastructure (agent tool credentials, vaults, MCP auth — identity+agent gap), AI Customer Support (support agents / case triage — Abnormal production case-triage transfer).

## These are clusters, not fully independent dimensions

Cross-market pattern transfer is the point (e.g. "agent eval" / memory / observability show up across developer + infra). Treat the list as ~3 ICP clusters × verticals. Use `pm.plan_recursive_fanout` + `pm.market_coverage` to track which parents still lack segments or analysed startups.

## Founder history inputs (drive personalisation)

The personal fit engine reads these to score every wedge. Keep them in one file the agent loads first each run.

- **Stack you can ship in a weekend**, which frameworks, which LLM providers, which infra you use fluently. Drives `technical_advantage` and `build_speed`.
- **Markets where you can name the top 10 players from memory**, drives `existing_knowledge`.
- **Distribution you already own**, audience, GitHub followers, past employers' networks, community memberships. Drives `distribution_fit`.
- **Cold-reachable buyer personas**, which titles/industries you can plausibly reach. Drives `sales_ability`.
- **What you'd work on free for 6 months**, drives `interest` (re-score quarterly, it drifts).

The interaction between this file and `personal-fit-score.md` is the whole point: founder history is the source of truth, personal-fit is its projection onto each startup.