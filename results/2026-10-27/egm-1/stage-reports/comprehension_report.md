# Comprehension Test: Click Analytics (Stage 6)

Target: `docs/designs/click_analytics.md`. FeatureRange 1..27, DetailedRange 28..34. Reviewer: `egm:egm-comprehension`.

**Verdict: fails the Re-Implementation Standard.** A fresh engineer could not write functionally identical code from this document without guessing.

## 🔴 Blocker

1. **Lines 28–34, plan.** Steps are bare phrases with no module names, signatures, schema, file paths, error behavior or tests. "Ship it" is not a step.
2. **Lines 19–21, storage and counter contract.**
   - No table name, columns, key type, connection config, DSN source or migration owner.
   - Behavior is undefined when a slug has no row yet.
   - The read-modify-write loses clicks under concurrency, and the doc does not say whether that is accepted.
   - Behavior is undefined if Postgres is down or slow, and whether the increment is synchronous.
   - No read path exposes counts, although the Objective (line 8) is to show them to owners.
3. **Line 23, "CEP" is undefined.** No expansion, event schema, transport, delivery guarantee, retry behavior, failure handling or definition of "downstream teams".
4. **Lines 25–26, bot detection.** There is no interface, plugin contract, model, inputs or outputs. It is unclear whether it runs in Phase 1. "Phase 1" is undefined. The doc does not say whether bot clicks are counted until a filter exists.

## 🟡 Major

5. **Line 14.** The method is `LinkStore.get(slug)`, not `get_url`.
6. **Line 13.** Slugs use SHA-256 (base62, 7 characters), not MD5. Slugs are deterministic, so two owners shortening the same URL share one count. The code has no owner concept, so "link owners" is undefined.
7. **Lines 18–19.** `resolve` returns `(302, url)` or `(404, None)`. The doc does not say 404s are not counted, where the increment goes, what happens if it raises, or how `resolve` gets a database connection (`store` is a module-level global).
8. **Line 23.** Click event fields are undefined (timestamp, user agent, IP). Privacy is unaddressed.
9. **Lines 8–9, 12–14.** No latency, throughput or accuracy requirements. The split between in-process links and Postgres counts is not stated as intentional.

## 🟢 Nit

10. **Line 4.** Author "example", status Draft, no date or reviewer.
11. **Line 8.** "Product" is undefined, with no success criteria or UI surface.
12. **Lines 12–14.** Code references have no links or anchors, and `create_link` is irrelevant to the design.
