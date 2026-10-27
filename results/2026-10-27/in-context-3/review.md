# Review: docs/designs/click_analytics.md

Reviewed against `shortener/api.py`, `shortener/slugs.py`, `shortener/store.py`, `tests/`.

## Blocker

1. **Lost updates in the increment.** "Reads the current count and writes back `count + 1`" is a read-modify-write. Two concurrent clicks on the same slug both read N and both write N+1, so clicks are lost. This directly breaks the stated requirement of exact, real-time numbers. Use an atomic `UPDATE ... SET count = count + 1` (or `INSERT ... ON CONFLICT DO UPDATE`), which is no more complex.

2. **Redirect availability is coupled to Postgres.** The count is incremented synchronously inside `resolve()` before returning. Today `resolve()` is an in-process dict lookup (`store.get`). After this change, a Postgres outage, failover, or latency spike makes every redirect slow or fail, including for links that never needed analytics. The doc does not say what `resolve` does when the increment fails (fail the redirect, or redirect and drop the count?). "Very reliable" is not a failure-handling design. The doc needs an explicit failure policy and a latency budget, or should move counting off the request path.

3. **The data model cannot deliver "per link owner" counts.** The Objective is to show *link owners* click counts, but the code has no owner concept: `create_link(url)` takes no user and `LinkStore` maps `slug -> url` only. Slugs are also deterministic (SHA-256 of the URL only), so two different owners shortening the same URL get the same slug and share one counter. The doc must define ownership and whether counts are per slug or per (owner, link).

## Major

4. **Background misstates the code (MD5).** The doc says slugs use MD5. `shortener/slugs.py:make_slug` uses SHA-256 (`hashlib.sha256`), and its docstring says so.

5. **Background misstates the code (`get_url`).** The doc cites `LinkStore.get_url(slug)`. The method is `LinkStore.get(slug)` in `shortener/store.py`; `get_url` does not exist. An implementer following the doc will hit an `AttributeError`.

6. **CEP is undefined and its failure mode is unspecified.** "Each click event is also forwarded to the CEP" gives no event schema, transport, delivery guarantee, or ownership. It also does not say whether the forward is synchronous. If it is, it adds a second hard dependency to the redirect path; if not, the doc should say how events are queued and what happens on failure. Readers outside the team (and future readers) cannot tell what it is. Spell it out once, even if briefly.

7. **Bot-detection framework is out of scope and unjustified for Phase 1.** An ML-based, pluggable framework "so that we can filter bot clicks in the future" is speculative generality: there is no requirement, training data, labeling approach, or success metric in the doc, and it conflicts with the "keep it simple" goal. It also contradicts "exact" counts if filtering later changes them. Leadership asked for it, so at minimum the doc should (a) record that as the reason, (b) define the Phase 1 deliverable narrowly (for example, record user-agent/IP on the click event so filtering is possible later), and (c) defer the framework to a later phase.

8. **Implementation plan is too thin to review or execute.** Four one-line steps ("Add a counter module", "Ship it") do not name files, the Postgres schema/migration, config and credentials for the analytics DB, a read path (how do owners *see* counts? there is no API or UI in the plan), tests, or rollout/rollback. The current code has no DB access, dependencies, or config, so the first step is not small. Step 3 also repeats the framework scope issue from #7.

9. **No read side.** The doc covers writing counts but never defines how counts are exposed to link owners (endpoint, auth, response shape, freshness), although that is the stated objective.

10. **Slug collisions interact with counting.** `make_slug` truncates the hash to 7 base62 characters, and `LinkStore.put` silently overwrites an existing slug. A collision would redirect one URL's slug to another and merge their counts. This is pre-existing, but click analytics makes it visible and the doc should at least note the assumption.

11. **State is in-process only.** `LinkStore` is an in-memory dict, while counts would be in external Postgres. Links vanish on restart while counts persist, and multiple instances would not share links. The doc should state how analytics rows relate to links that may no longer exist.

## Nit

12. **Which `resolve` outcomes count.** "When `resolve` succeeds" should be stated precisely: the 302 path only, not 404s. Say whether unknown-slug hits are tracked at all.

13. **Return shape.** The doc says `resolve` "returns the redirect"; it actually returns a `(status, location)` tuple. Describe the increment as happening before that return.

14. **Author and status.** Author is the placeholder `example`.

15. **Missing standard sections.** No non-goals, alternatives considered (async/batched counting, a counter in Redis), privacy implications of storing click events (IPs, user agents), or open questions.

16. **Test coverage not mentioned.** `tests/` only covers slugs. The doc should say how counting (especially concurrency) will be tested.
