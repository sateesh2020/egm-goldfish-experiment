# Review: `docs/designs/click_analytics.md`

Reviewed against `shortener/api.py`, `slugs.py`, `store.py`, `README.md`, and `tests/test_slugs.py`.

Severity: **Blocker** = the design cannot work or meet its stated objective as written. **Major** = significant gap or risk to fix before approval. **Nit** = minor or cosmetic.

## Blockers

1. **Read-then-write increment loses clicks under the documented deployment.**
   The design says the increment "reads the current count and writes back `count + 1`". The README says the web layer runs under 4 gunicorn worker processes, so concurrent clicks on one slug will interleave and overwrite each other. Counts will be silently low, and worst on popular links. Use an atomic statement (`INSERT ... ON CONFLICT (slug) DO UPDATE SET count = count + 1`), or append events and aggregate.

2. **No notion of a link owner exists, so the objective ("show link owners…") cannot be met.**
   `create_link(url)` takes no owner or user and `LinkStore` stores only `slug -> url`. The design adds no owner model, no ownership check, and no read API or UI for fetching counts. It covers only the write path.

3. **Counts are keyed by slug, but slugs are a deterministic function of the URL only.**
   `make_slug` hashes only the URL, so two owners shortening the same URL get the same slug and their clicks merge. The slug is also truncated to 7 base62 characters, and `LinkStore.put` overwrites silently, so two different URLs that collide would share a slug and a count. The design must state the identity being counted: per slug, per link record, or per owner and link. That likely requires changing slug or link generation.

4. **The analytics write sits synchronously in the redirect path, with no failure semantics.**
   "Increments … before it returns the redirect" means every redirect now depends on a remote Postgres owned by another team. A slow or unavailable analytics DB adds latency or turns successful redirects into errors. The design needs the failure behaviour spelled out: fire-and-forget, queue, or batch, with a timeout, and redirects must never fail because analytics did.

## Major

5. **The existing store is process-local, which undermines the design's base.**
   `LinkStore` is an in-memory dict created per process (`store = LinkStore()` in `api.py`). With 4 workers, a link created in one worker is not visible in the others, and state is lost on restart. The design builds on `resolve` without acknowledging this. Either state that persistent shared storage is a prerequisite, or note that clicks may be counted against links that only some workers know about.

6. **"CEP" is never defined and the forwarding is unspecified.**
   There is no expansion of the acronym, event schema, transport, delivery guarantee (at-least-once vs. best-effort), ordering, retry or failure behaviour, or owner. Forwarding inside `resolve` repeats the latency and availability problem from #4. Nothing says which downstream teams consume the events or why.

7. **Privacy and data handling are not addressed.**
   Click events sent to other teams likely include IP, user agent, or referrer, but the design lists no fields, retention, or consent and compliance review (GDPR, etc.). Fields and retention must be listed before events leave the service.

8. **The ML bot-detection framework is scope creep with no requirements.**
   The design says it is for filtering bots "in the future", yet it is in Phase 1 and the plan includes building a plugin interface. There are no goals, no labelled data, no accuracy targets, no latency budget, and no owner. Drop it from Phase 1 and record only what a later phase needs: raw events carry enough fields (user agent, timestamp) to filter later. Also define what a "click" is for now, e.g. whether HEAD requests, prefetches, or crawlers count.

9. **"Phase 1" is referenced but no phases are defined.**
   There is no Phase 2, no scope boundary, and no non-goals section.

10. **The implementation plan is not actionable.**
    "Add a counter module / Update the API / Ship it" has no file-level changes, no Postgres schema or migration, no connection management or config, no tests, no rollout or feature flag, no backfill (clicks before launch are not counted), and no monitoring. The plan is the only place these decisions could be pinned down, and it contains none.

11. **No dependency, ownership, or capacity plan for the data team's Postgres.**
    The design assumes write access to a shared database. It gives no expected write rate (every click is a write to one row, which becomes a hot row for popular links), no sizing, no agreement with the data team, and no credentials or config approach.

12. **Alternatives are not considered.**
    There is no comparison with, for example, an event log plus aggregation, Redis counters flushed periodically, or log-based analytics. Each avoids the hot-row and availability problems above.

## Nits

13. **Wrong hash named.** The Background says slugs use MD5, but `slugs.py` uses SHA-256 (the docstring and code agree). It does not affect the design, but it signals the doc was not checked against the code.

14. **Wrong method name.** The Background cites `LinkStore.get_url(slug)`. The actual method is `LinkStore.get(slug)`; `get_url` does not exist.

15. **Mixed reference style.** `resolve` returns `(status, location)` and is HTTP-agnostic, so "returns the redirect" is imprecise; the web layer builds the redirect. Say where the increment hook goes (in `resolve`, only when status is 302).

16. **Placeholder metadata.** Author is "example" and there are no reviewers, date, or links to a product requirement. There are no success metrics for the feature either, such as count accuracy or the latency added to redirects.

17. **No test strategy.** The only existing test file covers slugs. The design should name the tests expected for the counter, including a concurrency test for the lost-update case in #1.
