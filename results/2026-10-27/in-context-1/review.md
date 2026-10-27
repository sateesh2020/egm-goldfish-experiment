# Review: Click Analytics for Short Links

Reviewed `docs/designs/click_analytics.md` against `shortener/api.py`, `shortener/slugs.py`,
`shortener/store.py`, `tests/` and `README.md`.

## Blockers

1. **The read-then-write increment loses clicks.**
   The design reads the count and writes back `count + 1`. The README says the web layer runs
   `resolve` under 4 gunicorn worker processes, so concurrent clicks on one slug are normal. Two
   workers can both read N and both write N+1, which undercounts. Product asked for exact numbers.
   Use an atomic `UPDATE ... SET count = count + 1` (or `INSERT ... ON CONFLICT DO UPDATE`).
   A process-level lock would not help across 4 processes.

2. **Redirects depend on a synchronous write to an external database, with no failure behavior.**
   Today `resolve` is a pure in-memory lookup (`shortener/api.py:14-19`). The design adds a
   Postgres round trip, plus a CEP forward, before the redirect returns. If either is slow or
   down, every redirect is slow or fails. The doc says only that Postgres has been reliable. It
   does not say what `resolve` does on error or timeout (redirect anyway and drop or queue the
   count, or fail). It also does not set a latency budget or a connection pool, which 4 workers
   need. "Exact, real-time" has to be weighed against making the core redirect path depend on
   the data team's database.

## Majors

3. **Background misstates the code (slug hashing).**
   The doc says slugs use MD5. `shortener/slugs.py` uses SHA-256 (`hashlib.sha256`, and the
   `make_slug` docstring says so). Reviewers will distrust the rest of the Background.

4. **Background misstates the code (store API).**
   The doc cites `LinkStore.get_url(slug)`. The method is `LinkStore.get(slug)`
   (`shortener/store.py:16`). `get_url` does not exist.

5. **The doc never says where "click" is recorded or what it counts.**
   It says only "when `resolve` succeeds". It does not say whether the 404 path is counted, what
   happens for HEAD requests, prefetches or retries, or whether a click is one request. This
   matters because the number is meant to be exact.

6. **The CEP is undefined.**
   The doc forwards "each click event" to the CEP but never defines the term, links to it, or
   gives the event schema, delivery guarantee, or failure behavior. Calling it team knowledge is
   not enough for a design doc. The doc also doesn't say whether forwarding is synchronous (it
   adds to redirect latency) or whether a CEP failure can break a redirect.

7. **The ML bot-detection framework has no justification and no design.**
   Phase 1 adds a "pluggable, ML-based" framework "so that we can filter bot clicks in the
   future". Nothing in the doc uses it. It has no interface, data, model, or owner, and it
   changes no counts. It is speculative scope that adds risk and delay to a counting feature.
   Either cut it from Phase 1 (state bot filtering as a non-goal or future work) or give it a real
   design. If leadership's ask is the reason, record that and explain why the cheaper alternative
   (keeping raw click events, e.g. in the CEP, so filtering can be applied later) doesn't meet
   it.

8. **Implementation plan is not reviewable.**
   Four one-line steps ("Add a counter module", "Ship it") name no files, functions, schema,
   migration, config (DB DSN), tests, rollout, or rollback. Step 3 builds the speculative
   framework from item 7. There is no test plan, and the repo currently has only
   `tests/test_slugs.py`.

9. **No data model.**
   The doc doesn't give the table or key (per slug), whether counts are all-time or bucketed
   by time, or how the row is created for a new link. Link owners see counts, but nothing
   links a slug to an owner. `create_link` takes only a URL, and the doc doesn't address owners
   or auth.

10. **A multi-process store problem the design leans on.**
    `LinkStore` is an in-process dict (`shortener/store.py:10`). Under 4 gunicorn workers, each
    worker has its own copy, so a link created in one worker is not resolvable from the others.
    This predates the design, but click analytics sits on top of it: counts would be keyed by
    slugs that may 404 depending on which worker answers. The doc should at least note the
    dependency or say it's out of scope.

## Nits

11. **Missing sections.** There are no goals/non-goals, alternatives considered (e.g. async
    counting, batching), privacy or retention for click events (the CEP forwarding may carry IP
    or user agent), or monitoring and alerting.

12. **"Author: example"** is a placeholder.

13. **The doc doesn't mention `create_link` interaction.** `create_link` is cited in Background
    but never touched in the design. Say explicitly that it is unchanged, or that it initializes
    a counter row.

14. **Slug collisions are not discussed.** `make_slug` truncates SHA-256 to 7 base62 characters,
    so two URLs can map to the same slug, and `put` silently overwrites. Per-slug counts would
    then merge two links. This is a minor issue for analytics, but it undermines "exact" counts.
