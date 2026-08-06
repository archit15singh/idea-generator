# 08 / Query the OS

Natural-language queries over SID + Pattern Library + Problem Graph. Use a fixed query-template set. Refuse arbitrary SQL synthesis without confirmation.

## Supported templates

- "Show me every startup whose core dependency is `<PROBLEM>`."
- "Find `<MARKET>` startups with weak open-source competition."
- "Which markets have the highest concentration of successful `<X>` companies but the fewest OSS alternatives?"
- "List all patterns with `growth_rate > N` in the last 90 days."
- "Which wedges have `personal_fit.total >= 70` but `reply_rate < 5%`?" (re-wedge candidates)
- "Show me Problem Graph nodes with 2+ cross-source edges AND 3+ startups solving them that have NOT been promoted to the Pattern Library."

## Method (per query)

1. Resolve `<PROBLEM>`, `<MARKET>`, `<X>` against the controlled vocabulary first (`references/design/problem-graph.md`). If a term isn't in the vocab, refuse and ask for canonicalization. Don't free-text-match across the graph.
2. Compile to one SQL or one graph traversal. Print the plan before running. Ask the user to confirm if the query touches 20+ rows or writes/updates anything.
3. Return rows with hyperlinks to the raw scrape JSON for each startup.
4. Annotate each row with its state (saturating / active / retired) from the Pattern Library.

## When to run

On demand. This is what makes the dataset a reasoning engine rather than a directory. The output is for the founder, not the customer.

## Refs

- `references/design/startup-intelligence-os.md`: v0 through v3 build sequence (queries unlock at v2)
- `references/design/problem-graph.md`: the controlled vocabulary that makes resolution possible