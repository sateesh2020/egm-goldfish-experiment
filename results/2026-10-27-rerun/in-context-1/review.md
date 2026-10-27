# Review: docs/designs/click_analytics.md

Reviewed against the code in this repo (`shortener/api.py`, `slugs.py`, `store.py`, `README.md`, `tests/`).

## Blocker

1. **Lost updates in the increment.** The design reads the count and writes back `count + 1`. The README says the web layer runs `resolve` under 4 gunicorn worker processes, so concurrent clicks on one slug will interleave and overwrite each other. Counts will be too low, which contradicts the stated goal of "exact, real-time numbers". Use an atomic `UPDATE ... SET count = count + 1` or `INSERT ... ON CONFLICT DO UPDATE`. This is no more complex than the current design.

2. **Redirects depend on a remote database.** `resolve()` is currently a pure in-memory lookup. The design adds a synchronous Postgres write (owned by another team) and a CEP call to every redirect. If either is slow or down, redirects are slow or fail. The doc does not say what happens on failure, whether there are timeouts, or whether a failed count blocks the 302. "Postgres has been reliable" is not a failure-handling plan. At minimum, define timeouts and decide explicitly whether to fail open (redirect anyway, accept a missed count).

3. **The CEP forwarding has no contract.** The doc says each click goes to the CEP and doesn't explain it. It never states:
   - the event schema
   - the transport
   - delivery guarantees
   - ordering
   - failure behavior (it is also unspecified whether this call is synchronous)

   Nothing in the repo refers to a CEP. This is the second remote dependency on the redirect path (see 2), and a reviewer outside the team cannot evaluate it.

## Major

4. **Wrong hash in Background.** The doc says slugs use MD5. `shortener/slugs.py` uses SHA-256 (`hashlib.sha256`, base62, 7 chars). Fix the doc.

5. **Wrong method name in Background.** The doc cites `LinkStore.get_url(slug)`. `shortener/store.py` defines `LinkStore.get(slug)`, and `get_url` appears nowhere in the repo.

6. **Phase 1 scope includes speculative ML bot detection.** The doc adds a "pluggable, ML-based bot-detection framework" for filtering that is explicitly "in the future". The objective (per-link click counts) does not need it, and no data or labels exist yet. Plan item 3 ("Add the bot-detection plugin interface") is not specified at all: no interface, no input fields, and no consumer. Leadership's request needs to be reconciled with this. For example, record user-agent and IP/hash on the click event now, and defer the framework.

7. **No data model.** The doc says "counts live in the analytics database" but gives no table or schema, key, or index. It also leaves out:
   - who creates the table and who owns the migration
   - how the service gets credentials and connections (no DB client or config exists in the repo)
   - connection pooling across 4 workers
   - whether a count is per slug or per link (`make_slug` is deterministic per URL, so identical URLs share a slug and a count)

8. **Hot-row contention.** Every click on a popular link updates the same Postgres row inside the request path. Even with an atomic increment, this serializes on row locks. The doc doesn't address expected click volume or whether "exact real-time" justifies it versus an append-only events table with aggregation.

9. **Implementation plan is too thin to execute or review.** The four steps ("Add a counter module", "Update the API", "Add the bot-detection plugin interface", "Ship it") name no files, functions, or signatures. There is no testing step, even though the repo has a `tests/` directory (currently only `test_slugs.py`). It also has no rollout, feature flag, rollback, or monitoring. "Ship it" is not a step.

10. **No handling of the 404 path and counting semantics.** The doc says counts increment when `resolve` succeeds. It doesn't say whether 404s are tracked, whether HEAD requests, prefetches, or retried requests count as clicks, or how the count relates to what link owners see ("exact"). Without this, "exact" has no definition.

11. **Missing access and privacy considerations.** Click events forwarded to downstream teams may include IPs and user agents (bot detection implies this). The doc doesn't address data retention, PII, or who may read the counts. Link owners seeing counts also needs an authorization story, and none exists in this repo.

12. **Existing storage limitation interacts with the design.** `LinkStore` is an in-process dict, so each gunicorn worker has its own copy. A link created in one worker will resolve 404 in the others. This is a pre-existing problem and out of scope, but the doc should acknowledge it, since it affects which "successful resolves" get counted and where analytics are keyed.

## Nit

13. **Author is "example".** Replace with a real author.

14. **Terminology.** "CEP" is used without expansion in a doc other teams will read. Expand it once and link to its documentation, even if the team knows it.

15. **Missing standard sections.** There are no Goals/Non-goals, Alternatives Considered (for example async counting or an events table), or Open Questions. The two decisions that drive the design, synchronous exact counts and a simple increment, are presented without the trade-offs behind them.

16. **Vague wording.** "So downstream teams can use it" doesn't name which teams or what they need. Describe the consumers or drop the sentence.

17. **Status/Date metadata.** The header has no date or reviewers. Consider adding them for a design doc that is going to be reviewed.
