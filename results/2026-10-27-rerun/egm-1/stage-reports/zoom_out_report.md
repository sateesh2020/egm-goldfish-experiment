# Stage 5: Initial Zoom Out Report

**Target:** `docs/designs/click_analytics.md` (full file, lines 1-33)
**Reviewer:** `egm-zoom-out` (fresh Goldfish, direct dispatch)

## 🔴 Blocker

### ZO-1: Read-then-write increment loses clicks (lines 18-21)
* The design "reads the current count and writes back `count + 1`". `README.md` says the web layer runs 4 gunicorn worker processes, so concurrent clicks on one slug interleave and the count is undercounted. The same happens under threads.
* Recommendation: require an atomic increment in the database, stated as a requirement.

## 🟡 Major

### ZO-2: Background contradicts the code (lines 12-14)
* Says slugs use MD5; `slugs.py` line 9 uses SHA-256. Says `LinkStore.get_url(slug)`; the method is `LinkStore.get(slug)` (`store.py` line 16, called at `api.py` line 16).
* Recommendation: correct the Background; say whether the MD5 claim implies an out-of-scope change.

### ZO-3: Failure semantics of a synchronous cross-team DB write are unstated (lines 18-20)
* `resolve` has no I/O dependency today. An analytics outage or latency spike would slow or break every redirect.
* Recommendation: a failed count write is logged and swallowed and never fails the redirect. No queue until measurements justify one.

### ZO-4: Forwarding clicks to "CEP" is undefined and out of scope (line 23)
* CEP is not defined; no consumer, schema, delivery guarantee or failure behavior. Not needed for per-link counts. Adds a second synchronous dependency on the redirect path.
* Recommendation: remove from this scope.

### ZO-5: ML bot-detection framework is speculative (lines 25-26)
* No requirement or data showing bot traffic matters; Plan step 3 commits to building it.
* Recommendation: drop from Phase 1; keeping `resolve` as the single increment call site leaves room for a simple filter later.

### ZO-6: Read path, data flow and data-ownership rationale are missing (lines 6-8, 18-21)
* No statement of how owners read counts, no data flow, no reason for the data team's Postgres over a store beside `LinkStore`. `LinkStore` has no owner concept, so "link owners" implies ownership/auth the codebase lacks.
* Recommendation: add the user-visible outcome, read path, scope (total clicks only?), data flow and a one-row-per-slug data model.

### ZO-7: Implementation plan is not actionable (lines 28-33)
* "Add a counter module", "Update the API", "Ship it" give no interfaces, placement, tests or rollout. Step 3 builds the item in ZO-5.
* Recommendation: a counter interface called from `resolve`, failure-tolerant behavior, tests including a concurrency test, and a rollout/verification step.

## 🟢 Nit

### ZO-8: Layer placement of the increment is ambiguous (lines 18-19)
* `api.py` handlers are HTTP-agnostic and `resolve` returns `(status, location)`. Inject the counter behind an interface rather than hardcoding Postgres; `store = LinkStore()` is already a module global.

### ZO-9: Author is the placeholder "example" (line 4)
* No owner for open questions.

## Out-of-scope observation
`store.py` is in-process and there are 4 gunicorn workers, so each worker has its own `LinkStore` and a link created in one worker can 404 in the others. Do not assume `LinkStore` is a reliable shared store; raise separately.

**Counts:** Blocker 1, Major 6, Nit 2.
