# Personalisation + Founder History

The original instinct — analyze 100 random YC startups — optimizes for breadth. The reframe optimizes for **founder intuition in markets where you have an unfair advantage**.

## Why constrain the search space

- Random sampling produces a catalog. Constrained sampling produces a **mental model** of where value concentrates.
- The goal is not "ideas generated" — it is "intuition developed." Intuition is market-specific, not market-agnostic.
- Founder-market fit is the highest-leverage variable. Constraining to markets you already understand compounds your unfair advantages instead of fighting them.

## The 20 markets

| # | Market | Notes |
|---|--------|-------|
| 1  | AI Engineering               | Home turf |
| 2  | Cybersecurity                | Compliance + adversarial thinking overlap |
| 3  | Enterprise AI                | Slow buyers, high ACV, durable |
| 4  | Developer Tools              | PLG-friendly, distribution you know |
| 5  | Knowledge Management         | Memory/infra plays underneath |
| 6  | AI Infrastructure            | Cross-cutting platform layer |
| 7  | Agent Infrastructure         | Emerging, ill-defined, greenfield |
| 8  | Enterprise Automation        | Boring-but-valuable, clear ROI |
| 9  | B2B Productivity             | Crowded; wedge hunting matters |
| 10 | Technical Founder Tools      | Meta — you are the ICP |

## These are clusters, not 20 independent dimensions

- **ICP cluster A (developers/founders):** 1, 4, 7, 10 — you are the buyer.
- **Infra cluster B (platform primitives):** 5, 6, 7 — memory, eval, observability repeat across all three.
- **Buyer cluster C (enterprise IT/ops):** 3, 8, 9 — slow buy, high ACV, durable.

The overlap is the point: cross-market pattern transfer is where real signal lives ("agent eval" appears in 1, 6, 7, and 10). \> Treat the list as ~3 clusters × ~4 verticals, not 20 independent axes.

> **Risk:** if a future iteration keeps these 10, it is internally redundant. Either expand to genuinely orthogonal markets (healthcare, legal, climate) or explicitly rename this cluster "developer/enterprise-AI." Do not pretend they are independent.

## Founder history inputs (drive personalisation)

The personal fit engine reads these to score every wedge. Keep them in one file the agent loads first each run.

- **Stack you can ship in a weekend** — which frameworks, which LLM providers, which infra you use fluently. Drives `technical_advantage` and `build_speed`.
- **Markets where you can name the top 10 players from memory** — drives `existing_knowledge`.
- **Distribution you already own** — audience, GitHub followers, past employers' networks, community memberships. Drives `distribution_fit`.
- **Cold-reachable buyer personas** — which titles/industries you can plausibly reach. Drives `sales_ability`.
- **What you'd work on free for 6 months** — drives `interest` (re-score quarterly, it drifts).

The interaction between this file and `personal-fit-score.md` is the whole point: founder history is the source of truth, personal-fit is its projection onto each startup.