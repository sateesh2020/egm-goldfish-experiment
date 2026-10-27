# Review: docs/designs/click_analytics.md

Reviewed against `shortener/api.py`, `shortener/slugs.py`, `shortener/store.py`, `README.md`.

## Blocker

1. **Read-modify-write counter loses clicks.** The design says the increment "reads the current count and writes back `count + 1`". The README says the web layer runs `resolve` under 4 gunicorn worker processes, so concurrent clicks on the same slug will read the same value and overwrite each other. Counts will be undercounted, most for popular links. Use an atomic increment (`UPDATE ... SET count = count + 1`, or `INSERT ... ON CONFLICT DO UPDATE`). An in-process lock would not help, because the workers are separate processes.

2. **Counting happens synchronously on the redirect path, with a failure mode that isn't addressed.** The count is incremented "before it returns the redirect" against a Postgres instance hosted by another team. `resolve` is currently a pure in-memory lookup. If that database is slow or down, every redirect slows down or fails, and the design doesn't say what should happen. Decide that analytics failures must never break redirects, and either write asynchronously (queue or batch) or use a short timeout and swallow errors. Also decide whether the increment happens before or after the 404 check. The design only says "when `resolve` succeeds".

3. **Cross-team dependency that isn't scoped.** The analytics DB is owned by the data team, but there is no schema, capacity estimate (writes per second, one row-hot per popular slug), access or credentials, or sign-off from them. Per-click writes to one hot row make the contention in item 1 worse.

## Major

4. **Background references code that doesn't match the repo.**
   - `LinkStore.get_url(slug)` doesn't exist. The method is `LinkStore.get(slug)`, and `resolve` calls `store.get`.
   - Slugs are not generated with MD5. `make_slug` uses SHA-256.
   These errors suggest the design was written from memory. Fix them, and re-check that the integration points are right.

5. **"CEP" is never defined.** The term is not defined or linked, and nothing in the repo refers to it. The design doesn't say the event schema, the transport, delivery guarantees (at-least-once or best-effort), or whether forwarding is synchronous. It also doesn't say what happens when forwarding fails. It adds a second external dependency to the redirect path with the same risks as item 2. Also, forwarding raw click events to "downstream teams" has privacy implications (IP, user agent, referrer) that aren't discussed.

6. **Scope creep: ML bot-detection framework in Phase 1.** The objective is a click count. The design adds a "pluggable, ML-based bot-detection framework" for filtering "in the future", with no requirement or owner behind it. That is speculative, and plan step 3 builds an interface for it. Remove it from Phase 1. If bot filtering matters, make it a separate design. Recording user agent or IP with each click would keep the option open.

7. **State is not shared between workers or restarts.** `LinkStore` is in-process, so each of the 4 workers has its own `_links`. A link created in one worker returns 404 from another. A restart loses all links. This is an existing problem, but it affects this design: analytics keyed by slug would be recorded for links that may not be resolvable consistently. The design should at least acknowledge it, or state that the link store moves to shared storage first.

8. **Slug collisions and truncation affect count integrity.** `make_slug` keeps only 7 base62 characters (about 3.5e12 values) derived from the URL, and `put` overwrites silently. Two different URLs that collide share a slug, and therefore share a counter. Also, the same URL always has the same slug, so two different owners shortening the same URL share one count. The design says counts are shown to "link owners", but there is no owner concept in the code. Define what a "link owner" is, or state that counts are per slug.

9. **Missing requirements and semantics.** The design doesn't say:
   - What counts as a click, such as HEAD requests, prefetching, bots (see item 6), or repeat clicks from the same visitor.
   - How owners read the counts. There is no read API, endpoint, or UI in the plan.
   - Retention and granularity (total only, or per day).
   - How the counter is initialised for existing links.
   - Whether exactly-once or approximate counting is acceptable.

10. **The implementation plan is not actionable.** The four steps ("Add a counter module", "Update the API", ...) have no detail. "Ship it" is not a step. There is no rollout (feature flag, backfill), migration, testing strategy, or monitoring. There is also no test plan, and the only existing tests cover slugs. Concurrency, DB-down behavior, and the 404 path should be tested.

## Nit

11. The design says "Phase 1" but no other phase is defined.
12. Status is "Draft" with a placeholder author ("example"), and there is no reviewer list or date.
13. "Objective" lacks success criteria or non-goals.
14. Name the module and the function signatures (for example, `shortener/counter.py`, `record_click(slug)`) so the plan can be checked against the code.
15. `resolve` is described as returning "the redirect". Its real return value is `(status, location)`, because it is HTTP-agnostic. The design should say where the increment sits relative to that.
