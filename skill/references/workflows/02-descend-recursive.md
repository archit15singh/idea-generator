# 02 / Descend

Run a one-pass 10-level descent per startup. The descent is a concentration funnel, not a checklist. Each level is a strict subset of the one above.

## Do (per startup, one descent)

Produce one short answer per level. Read inputs from the SID row produced by `01-ingest.md`.

| L  | Question | Notes |
|----|----------|-------|
| L1  | What are they selling?                      | commodity; answer in one line |
| L2  | What problem are they solving?              | from `startup_problem.core_problem` |
| L3  | Why does this problem exist?                | root cause, not restatement |
| L4  | Why hasn't it been solved?                  | structural blockers |
| L5  | What changed recently?                     | spend disproportionate time here. List 3+ enabling shifts (model capability, regulation, supply, distro, pricing collapse). No L5 means no wedge. |
| L6  | Which customer suffers most?                | rank by willingness-to-pay × frequency, NOT severity |
| L7  | Can I solve only 20% of this?               | the 20%-slice of L6 |
| L8  | Can AI solve that 20%?                       | strict subset of L7 |
| L9  | Can open source solve it?                   | strict subset of L8 |
| L10 | Can infra solve it once for everyone?        | rare; do not force. Forced L10 is infra for its own sake. |

Most descents terminate at L7 or L8. Forcing L10 produces infrastructure-shaped PR, not businesses.

## Output

Store the path as one JSON blob on `startups.recursive_path` (or a dedicated side-table). Only L5 / L6 / L7 outputs graduate into the wedge table. L10 hits are flagged as `infrastructure_ops` candidates.

## Refs

- `references/design/recursive-framework.md`: the per-level rules
- `references/design/analysis.md`: the L5 emphasis and the L7-L10 funnel argument