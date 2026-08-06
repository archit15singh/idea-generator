# The Recursive Framework

Run this 10-level descent per startup. The descent is a **concentration funnel**, not a checklist of alternatives — each level is a strict subset of the one above.

```
L1  What are they selling?
L2  What problem are they solving?
L3  Why does this problem exist?
L4  Why hasn't it been solved?
L5  What changed recently?                      ← wedge generator
L6  Which customer suffers most?
L7  Can I solve only 20% of this?
L8  Can AI solve that 20%?
L9  Can open source solve it?
L10 Can infrastructure solve it once for everyone?   ← platform ideas live here
```

## Stage-by-stage rules

- **L1–L4 — decompositional analysis.** Commodities. Do it once per startup, do not belabor it.
- **L5 — the actual wedge generator.** "What changed recently" is the only level that creates novel opportunity; everything else rearranges known supply. **Spend disproportionate time here.** List 3–5 specific enabling shifts per startup: model capability, regulation, supply chain, distribution channel, pricing collapse. No L5 ⇒ no wedge.
- **L6 — narrow to the suffering customer.** This is where most YC-style theses actually anchor. Rank by **willingness-to-pay × pain frequency**, not pain severity. Severity without willingness-to-pay is charity, not a market.
- **L7–L10 — concentration funnel.** L7 is the 20%-slice of L6. L8 is the AI-solvable subset of L7. L9 is the OSS-solvable subset of L8. L10 is the infra-solvable subset of L9. Most descents terminate at L7 or L8.
- **Do not force L10.** A forced L10 produces infrastructure for its own sake. An L10 hit is rare but compounding — when it lands, it is usually the best business in the dataset, but that is precisely because most descents don't reach it honestly.

## Output

The descended path is stored as a single JSON blob on the `startups.raw` or a dedicated `recursive_path` text column (one row per startup), so each level's answer is queryable. The selected wedge (from `factory.md` Stage 3) is the one level that graduates into the `wedges` table.