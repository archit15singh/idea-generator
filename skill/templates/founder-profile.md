# Founder Profile

**The scorer reads this file. Without it filled in, every personal_fit score is fiction.**
Edit before first run. Re-edit quarterly, `interest` and `distribution_fit` drift fastest.

## Stack I can ship in a weekend
<!-- List frameworks, LLM providers, infra you use fluently. Drives technical_advantage + build_speed. -->

**Languages (production-fluent):** Python (8+ YOE, primary), Go (Abnormal attack-detection heuristics), Rust (Memori — 43µs reads, SQLite FTS5+vector core), TypeScript (basic, MCP servers).

**Backend & data:** Postgres + pgvector (memory/search at Abnormal), Redis (state machines, caching, observability UI — acquired by Redis Inc and folded into RedisInsight), Kafka (10M+ events/month ingestion), Postgres CDC, Celery, Prefect, Airflow, Databricks.

**Streaming & realtime:** Kafka ingestion pipelines, async-safe orchestration, cross-region replication, OpenTelemetry tracing, Prometheus, SLA dashboards.

**Cloud & IaC:** AWS (ECS, CloudWatch, S3, Lambda), Terraform (basic), Docker, Kubernetes (basic), GitHub Actions.

**AI/LLM infra:** OpenRouter, Anthropic, OpenAI, pgvector hybrid search (FTS5 + vector), embedding pipelines, agent loop design (tool registry isolation, sub-agent pattern, policy engine, memory capture/retrieval/decay).

**Agent frameworks I have shipped/forked:** Letta/MemGPT (forked), Composio (forked), Pydantic AI (forked), container-use (forked), Graphiti (forked), MCP server browserbase (forked). Built Hermes Agent (powers Luffy) + Memori (Rust+SQLite memory) + Sim Bangalore (Rust agent-based digital twin).

**Web (one weekend slice):** FastAPI, Jinja/Tailwind CDN single-file, basic React. Frontend is NOT home turf — pair or keep minimal.

## Markets where I can name the top 10 players from memory
<!-- Drives existing_knowledge. Be honest about gaps. -->

**AI agent memory (home turf — strongest):** Letta/MemGPT, Zep, Mem0, Graphiti (getZep), Memori (mine), LangChain memory, LlamaIndex memory, Cursor's memory, Cognition's Devin memory, Redis-variant memory stores. I gave a PyCon India 2025 talk on this.

**Email/BEC/fraud detection (day job at Abnormal AI):** Abnormal, Proofpoint, Mimecast, MSG Copy, Check Point, Barracuda, Tessian, Egress. Vendor-fraud case triage agent shipped to multi-region production (96% QA pass rate, 7x turnaround improvement).

**Distributed streaming/observability:** Kafka, Redpanda, ClickHouse, OpenTelemetry, Prometheus, Grafana, Sentry, Datadog, Honeycomb. Built a Redis-based observability platform that was acquired by Redis Inc (folded into RedisInsight).

**Redis ecosystem deep:** Redis, RedisInsight, Redis Stack, Upstash, Momento, Valkey. Author of acquired redis-gui.

**Vector search space:** pgvector, Pinecone, Weaviate, Qdrant, Chroma, Milvus, LanceDB. Built Postgres/pgvector memory at Abnormal for reasoning-grade retrieval.

**Detection & entity-scoring pipelines (built at Abnormal):** breaking messages into granular entities, feature stores, heuristic development, high-recall signals for ML models.

**GAPS — I cannot name top 10 from memory:** Fintech infra (Stripe/Twilio-adjacent), healthcare HIPAA-specific tooling, legaltech SaaS, climate/carbon, CRM, HRIS, sales-eng tooling outside email security, anything requiring Spanish/LATAM or Chinese-market knowledge.

## Distribution I already own
<!-- Audience, GitHub followers, past employers' networks, communities you moderate. Drives distribution_fit. -->

- **GitHub:** 53 followers, 142 repos, 1.6k stars, public sponsor, Pull Shark x3, Starstruck achievement. Memori (Rust memory for AI agents), Luffy (PR review agent), Sim Bangalore (digital twin). Open-source distribution is real.
- **LinkedIn:** 8,581 followers, 500+ connections, 1,655 post impressions/7d, 774 profile views/7d, 170 search appearances/7d. Posts on AI agents, memory architecture, PyCon lessons — high-signal to other infra/AI engineers.
- **Personal blog:** archit15singh.github.io — "Building Systems from First Principles." ~9 long-form engineering posts (Memori architecture, recursive-design-of-agent-memory, hard-constraints-belong-in-code, designing-CLI-tools-for-ai-agents, AI-augmented-developer-playbook, Luffy PR review agent, who-am-i, reading-list, forging-AI-memory). Indexed on GitHub + shared on LinkedIn.
- **Speaker:** PyCon India 2025 — "Memory in AI Systems" (Redis, Postgres/vector memory, the control surface of AI agents). Slides + demo code published. Folks stopped me in corridors afterward to debate auditability.
- **Abnormal AI AI Champions program** — internal cross-team builder community I'm an active member of; Singapore build-week alum.
- **Past employer networks:** Tarka Labs (consulting), Droice Labs (clinical data), Nutanix/HashedIn (distributed infra). Reaches backend/distributed-systems engineers in Bengaluru.
- **Buyer-persona overlap:** the AI infra / agent infra ICP is me and my GitHub feed. I broadcast to it natively, not to recruiters or end-users.

## Cold-reachable buyer personas
<!-- Which titles/industries you can plausibly reach cold. Drives sales_ability. -->

**Strong (I can reach cold, they'll reply):**
- Senior/staff backend & platform engineers at AI-first startups (my GitHub + LinkedIn reach them directly)
- Infra/platform team leads at Bengaluru startups (Tarka/Nutanix/Droice network)
- Detection/security engineers at email-security or fraud-detection companies (Abnormal peer network)
- Engineers running agent eval / observability in production (PyCon, AI Champions reach)

**Reachable with effort:**
- Head of Platform / VP Eng at AI infra startups (need a warm intro; my blog posts are the wedge)
- Open-source maintainers of agent frameworks (I've forked their work — credible cold email)

**Weak / not reachable:**
- CISOs / security buyers at Fortune 500 (my reach is eng, not CISO)
- Enterprise IT procurement (I have zero enterprise-sales motion)
- Consumer product buyers (no consumer channel; consumer is a non-goal)

## What I'd work on free for 6 months
<!-- Drives interest. Re-score quarterly, it will change. -->

1. **AI agent memory infrastructure** — Memori, the PyCon talk, the "memory IS the control surface of an agent" thesis. I would build this free for years, not months.
2. **Hard-constraints-in-code + policy engines for agents** — wrote a whole blog post about the probabilistic-deterministic hybrid pattern; Luffy uses a policy-engine rule-interlock pattern before destructive tool calls.
3. **Agent observability / tracing** — the "agentic loop export as artifact" thesis (Luffy exports every run as a golden-trace artifact). Loop detection, context compression, next-speaker validation — I outlined a 6-part series on production agent patterns.
4. **Eval platforms for agents** — picked "Evals First, Code Later" at PyCon as a brain-rewiring session. Golden traces > unit tests for agent regression.
5. **Persistent context for coding agents** — Memori's whole reason for existing. The "every AI coding agent session starts from zero" tax compounds invisibly.

The aesthetics across all five: **memory, control, observability, eval, audit trails** for agent systems. These are NOT consumer-facing; they are the platform layer underneath every agent product.

## Notes / non-goals
<!-- Anything you refuse to work on, or constraints the scorer should respect. -->

**Non-negotiable non-goals:**
- **No consumer-social** (no TikTok-for-X, no dating, no consumer gamification). I have no consumer distribution channel.
- **No no-code / low-code end-user builders** — I do not enjoy frontend-for-non-engineers design.
- **No pure-marketing / SEO / growth-hacking tools.** Not my skill, not my interest.
- **No B2B SaaS where the moat is Salesforce seat count** — I do not want to sell to enterprise procurement.

**Constraints that constrain the scorer:**
- Bengaluru, India based. **Currently full-time at Abnormal AI** (Senior SWE, Attack Detection team, started Sep 2025). Any idea-factory wedge must be side-project-first, shippable in weekend slices, NOT competing with Abnormal's email-security business. No conflict-of-interest with my employer.
- I prefer platforms/infra (PaaS-style, devtools) over vertical apps. The convergent layers the meta-loop surfaces (Memory, Connectors, Cost optimization, Tracing/observability, Authentication, Retrieval/RAG, Evaluation) are exactly where I'd bet my career — horizontal infrastructure that many applications need.
- I value a 60 that is 10/10/2/8/10/10/2/8 (sharp shape) over a 60 that is 5/5/6/6/6/6/6/20-impossible. Shape > number. The scorer should surface shape outliers in `shape_outliers`, not flatten them.
- I do not want to fundraise before a working wedge has paying or pain-signal-validated customers. Validation before build, no exceptions.

**What the scorer should WEIGHT toward given this profile:**
- `technical_advantage` and `build_speed` should be 9-10 for any wedge that touches (agent memory OR Postgres/pgvector OR Redis state machines OR Rust+SQLite OR Python/Kafka streaming). I have shipped all of these to production.
- `existing_knowledge` should be 9-10 for agent infra / memory / detection pipelines / streaming; 2-5 for anything else.
- `distribution_fit` should be 7-9 for open-source-led dev infra (I have the OSS lineage), 4-6 for B2B startups (LinkedIn reach is engineers, not execs), 1-2 for enterprise IT procurement.
- `interest` should be 10 for memory/eval/observability/policy/control-surface wedges, 1-3 for anything web3/CRM/recruiting/marketing.
- `long_term_moat` — wedges that compound (memory capture, eval data, audit-artifact traces, knowledge graphs) score high; feature-parity races score low.
- `market_size` — convergent infrastructure layers (used by ≥half of an analysed YC cohort) are by construction large TAM; per-startup vertical wedges need explicit expansion-path evidence.
- `sales_ability` — cold-reachable to infra/platform/detection eng, weak to CISO / enterprise IT. Score accordingly.