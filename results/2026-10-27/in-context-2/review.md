# Review: docs/designs/click_analytics.md

Reviewed against `shortener/api.py`, `shortener/slugs.py`, `shortener/store.py`,
`tests/test_slugs.py` and `README.md`.

## Blocker

1. **Read-then-write increment loses clicks.** The design reads the count and
   writes back `count + 1`. `README.md` says the web layer runs `resolve` under
   4 gunicorn worker processes, so concurrent clicks on one slug will read the
   same value and overwrite each other. No in-process lock helps, because the
   workers are separate processes. That contradicts the stated goal of exact
   numbers. Fix: use an atomic `UPDATE ... SET count = count + 1` (or
   `INSERT ... ON CONFLICT DO UPDATE`) in a single statement.

2. **Synchronous Postgres write puts an external DB in the redirect path.**
   `resolve` today (`api.py:14-19`) is a pure in-memory lookup. The design adds
   a network write to the data team's Postgres before returning the redirect,
   and a CEP forward on top of that. The doc doesn't say what happens when the
   write is slow or fails: does the redirect fail, or is the click dropped? A
   dependency outage or latency spike would take down all redirects. "Has been
   reliable" is not a failure-mode design. Define the timeout and failure
   behaviour, or count off the hot path.

3. **The storage layer can't support click counting as it stands.**
   `LinkStore` is an in-process dict (`store.py:9`). With 4 worker processes,
   each has its own copy, so a link created in one worker returns 404 in the
   others. The doc is silent on this. It affects the feature directly, because
   counts for a slug can only be attributed correctly if the link resolves
   consistently. The design should either state that the store is being
   replaced or explain why this is out of scope.

## Major

4. **Background states the wrong hash.** The doc says slugs use MD5;
   `slugs.py:2,10` uses SHA-256.

5. **Background names a method that doesn't exist.** The doc says
   `LinkStore.get_url(slug)`; the method is `LinkStore.get(slug)`
   (`store.py:16`). The design's reference to the hook point is therefore wrong.

6. **"The CEP" is undefined and its contract is unspecified.** The doc never
   expands the acronym. It also gives no event schema, delivery guarantee
   (sync or async, at-least-once or best-effort), or behaviour on failure. "So
   downstream teams can use it" is not a requirement. The doc will outlive the
   team's shared context.

7. **Bot-detection framework is scope creep with no design.** Phase 1 adds a
   pluggable ML framework that nothing consumes. The doc doesn't define the
   plugin interface, inputs, or what "ML-based" means, and the Objective never
   mentions bots. Counting is synchronous, so a model in that path would add
   latency to every redirect. Either cut it from Phase 1 or give it its own
   section. A minimal alternative is to record user-agent and IP with each
   event so filtering can be added later without a framework.

8. **Implementation plan is not actionable.** The four steps ("Add a counter
   module", "Update the API", ..., "Ship it") name no files, schema, migration,
   tests or rollout. There is no Postgres table definition or connection
   configuration. Nothing covers testing; the repo's only tests are for slug
   generation. Step 4 "Ship it" isn't a plan.

9. **No definition of what counts as a click, or how owners read the counts.**
   The Objective says owners should *see* counts, but the design only writes
   them. There is no read API, no ownership model (the store has no owner
   concept), and no handling for 404s, repeated clicks or HEAD requests.

10. **Doc doesn't mention the existing slug-collision behaviour.** `make_slug`
    truncates the SHA-256 to 7 base62 characters, and `LinkStore.put` silently
    overwrites an existing slug (`store.py:14`). Two URLs that collide share one
    slug and one click count, and the second silently replaces the first. Counts
    keyed by slug inherit this problem, and the doc should say so or address it.

## Nit

11. **Author is the placeholder `example`.**

12. **Status "Draft" with no reviewers, date or open-questions section.**

13. **Background says slugs are "generated with MD5"** as a design-relevant
    fact. If the hash is not relevant to analytics, drop it rather than keep a
    wrong statement (see item 4).

14. **"Phase 1" is used without defining other phases.** The Design refers to
    "Phase 1" but no later phase exists in the doc.

15. **Inconsistent terminology:** "click count", "click event" and "increment"
    are used without defining the stored data model (per-slug total vs. event
    log).
