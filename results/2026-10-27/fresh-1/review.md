# Review: docs/designs/click_analytics.md

Reviewed against the code in `shortener/` and `README.md`.

## Blocker

1. **Read-modify-write counter loses clicks (Design, para 1).** "Reads the current count and writes back `count + 1`" is a race. The README says the web layer runs 4 gunicorn worker processes, so concurrent clicks on one slug will overwrite each other and undercount. It needs an atomic increment (`UPDATE ... SET count = count + 1`, or `INSERT ... ON CONFLICT DO UPDATE`), or an append-only events table aggregated later.

2. **Synchronous write to an external Postgres on the redirect path.** `resolve` is currently a pure in-memory lookup. The design makes every redirect wait on a remote database owned by another team. A slow or unavailable analytics DB would slow or break redirects, and the doc has no failure mode (timeout, drop, or queue). Counting should be async or best-effort and must never fail the redirect.

3. **The design has no stated behaviour for the failure cases above and no data model.** There is no table schema, no key (slug vs. link), no connection or pooling plan, and no description of how link owners read the counts (API, UI, auth). The stated objective ("show link owners how many times each link was clicked") is not covered by the design: it only writes counts. The code also has no concept of an owner, so ownership and authorization are missing entirely.

## Major

4. **Wrong method name.** Background says links are read with `LinkStore.get_url(slug)`. The method is `LinkStore.get(slug)` (`shortener/store.py:16`, called at `shortener/api.py:14`).

5. **Wrong hash algorithm.** Background says slugs use MD5. `shortener/slugs.py` uses SHA-256 (`make_slug`, docstring and body).

6. **"CEP" is undefined and has no contract.** Forwarding each click to the CEP is not defined: expansion, transport, schema, delivery guarantees, PII (IP, user agent), and failure handling are all missing. It is also outside the stated objective. Either specify it or drop it.

7. **Scope creep: ML bot-detection framework in Phase 1.** A "pluggable, ML-based" framework for filtering "in the future" is speculative, has no requirements, and is unrelated to the objective. Remove it or defer it to a separate design. Raw counts that include bots will also be shown to owners in the meantime, so the semantics of a "click" should be defined.

8. **Slug collisions and truncation affect counts.** `make_slug` keeps only 7 base62 characters of a SHA-256-derived value. Different URLs can collide on a slug, and `create_link` silently overwrites (`store.put`). Counts keyed by slug would then be merged across different links. The design should note this or key counts differently. The slug is also a pure function of the URL, so two owners shortening the same URL share one slug and one counter, which conflicts with per-owner analytics.

9. **Storage is in-process, so state differs per worker.** `LinkStore` is a per-process dict. With 4 workers, a link created in one worker is not visible in the others, so `resolve` may return 404 regardless of analytics. The design builds on `resolve` succeeding without noting this.

10. **Count only on success is under-specified.** Only 302s should count, but the doc doesn't say whether 404s, HEAD requests, prefetches or retries are counted, or whether counting is idempotent.

## Nit

11. **Implementation plan is not actionable.** The four steps ("Add a counter module", "Update the API", "Ship it") have no owners, files, tests, migration, rollout, or rollback. "Ship it" is not a step.

12. **No testing plan.** Existing tests cover only `slugs.py`. There is no plan for concurrency, DB-failure, or `resolve` tests.

13. **Unspecified metadata.** The status is "Draft" with a placeholder author ("example"), and there are no reviewers or dates. There is also no non-goals, privacy, retention, or monitoring section.

14. **Terminology.** "Phase 1" is used but no other phases are defined.
