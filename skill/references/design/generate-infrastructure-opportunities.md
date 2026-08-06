# Generate Infrastructure Opportunities

**Prompt:** "What internal platform did this startup have to build?"

Applications force their builders to construct platform-shaped internals, evaluation, memory, connectors, that usually have **broader applicability than the application itself**. Surfacing these is the cheapest source of platform ideas: someone already paid to build it, you reuse the primitive.

## Canonical internal platforms

Evaluation · Prompt management · Memory · Authentication · Connectors · Knowledge graph · Scheduling · Cost optimization · Tracing/observability · Retrieval/RAG

## Per-row fields

- **internal_platform**, controlled vocabulary (the list above)
- **description**, *why* they had to build it (which product constraint forced it), not just that they built it
- **broader_applicability**, 0/1 flag: does this primitive plausibly serve ≥2 other markets from the 20? Set 1 only with a one-line example pairing.
- **evidence**, cite the `startup_technical` row fields (memory / agents / evaluation / observability) that imply it

## Generation rules

1. **Infer from the technical row, don't invent.** If `memory` is non-null and complex, "Memory" is a candidate. If `evaluation` is null, do NOT emit "Evaluation", absence is signal.
2. **One platform per forcing function.** If two rows argue for the same platform for different reasons, emit two rows with different descriptions (delete-then-insert preserves order).
3. **broader_applicability=1 is rare and high-value.** Err toward 0; flipping to 1 needs an explicit cross-market pairing.

## Output

Upsert into `infrastructure_ops`, keyed on `(startup_id, internal_platform)`. A `broader_applicability=1` row is the seed of a Pattern Library entry (see `pattern-library.md`), promote after ≥3 cross-market repeats.