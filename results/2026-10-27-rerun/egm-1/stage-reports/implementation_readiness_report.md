# Stage 9: Implementation Readiness Report

**Target:** `docs/designs/click_analytics.md` (DetailedRange 28-33; lines 1-27 read for context)
**Reviewers:** `egm-implementation-readiness`, `egm-codebase-details`, `egm-style` (fresh Goldfish, direct dispatch), standard `implementation-readiness-standard`.
**Verdict:** FAIL. The plan is four one-line steps and fails the Zero-Decision Rule, Target Scope, Actionable Steps, Phasing and Test Plan requirements. Lens tags: R = readiness, C = codebase details, T = style.

## 🔴 Blocker

### IR-1: No file-level target scope or actionable steps (lines 30-33) [R, C, T]
No file is listed to create, modify or delete. "Counter module", "the API" and "plugin interface" have no path, class, function name or signature. No dependency (Postgres driver), configuration (DSN, env vars) or acceptance condition per step. `shortener/__init__.py` is empty, so no package exports exist. The repo has no dependency manifest (verified: no requirements, pyproject or setup file).

### IR-2: Counter storage and concurrency undefined (line 30) [R, C]
Read-then-write (design lines 18-21) loses updates under 4 gunicorn workers (`README.md:2`). Specify an atomic `INSERT ... ON CONFLICT DO UPDATE SET count = count + 1`. Missing: table name, schema, primary key and column type vs `MAX_SLUG_LEN = 16` (`store.py:4`), DDL/migration and its owner (data team hosts the DB), connection handling (pooling, DSN source, credentials), the module API (e.g. `record_click(slug)`), local/test environment without the data team's DB. A per-process in-memory structure would be wrong across workers.

### IR-3: `resolve` change and failure behavior unspecified (line 31) [R, C]
No statement of where in `resolve` (`api.py:14-19`) the call goes, how the counter is injected (module-global `store` at `api.py:5`), the fail-open/closed decision, timeouts, retries, or latency impact. Count only on 302, not 404. `resolve` returns `(302, url)`; no redirect is issued in this repo and the web layer is not in it (`README.md:2`).

### IR-4: Background contradicts the code (lines 12-14) [R, C]
`LinkStore.get`, not `get_url` (`store.py:16`, `api.py:16`); SHA-256, not MD5 (`slugs.py:9-10`). An implementer or test writer following the doc fails.

### IR-5: CEP forwarding is in the design (line 23) but has no plan step [R, C, T]
"CEP" is undefined and appears nowhere in the code. No transport, endpoint, event schema, auth, delivery guarantee, timeout or retry; no behavior when forwarding fails.

### IR-6: Bot-detection step is out of scope, undefined and contradictory (line 32) [R, C, T]
Design defers filtering to "the future" but the plan ships the framework now with no consumer. No interface, discovery mechanism, input features or default. `resolve(slug)` receives only a slug, so there is no request metadata to detect on. Remove, or specify a minimal stub (a `BotDetector` Protocol with a no-op default). "Plugin interface" and "framework" are used interchangeably and neither is defined. (Severity: Blocker per readiness lens; Major per codebase and style lenses.)

### IR-7: "Ship it" is not a step (line 33) [R, C, T]
No deploy procedure, rollout, feature flag, rollback, migration ordering (table before code), environment configuration or definition of done; unclear who ships what given other teams own the schema and CEP.

### IR-8: No phasing or checkpoints (lines 30-33) [R, C, T]
"Phase 1" is named but no phases are defined. Nothing states the codebase state after each step. Step 3 is independent of steps 1-2 and no ordering is given.

### IR-9: No test plan (lines 30-33) [R, C]
Cases needed: successful resolve increments by 1; 404 does not increment; concurrent increments are not lost; database failure; CEP failure and payload; bot-detector default. Decide real Postgres vs fake vs in-memory. A `tests/` directory exists with `tests/test_slugs.py` (verified), covering only `make_slug`; nothing covers `api`, `resolve` or `store`, and no runner config exists. (The readiness lens stated there was no `tests/` directory; that was incorrect, and the codebase lens was right.)

## 🟡 Major

### IR-10: Counter semantics unspecified (line 30) [R, C, T]
Total only vs unique/daily/timestamped; whether `create_link` initializes a row; slug collisions. `make_slug` is a 7-char truncation and `put` silently overwrites (`store.py:14`), so counters keyed by slug can merge for unrelated URLs; state whether this is accepted. "Counter" does not say whether the module is a DB access layer, in-memory counter or event publisher.

### IR-11: Persistence mismatch (design lines 18-21 vs `store.py:9`) [R, C]
Links are in an in-process dict; counts would be in Postgres. After restart counts can reference slugs that no longer resolve, and each worker has its own links. No reconciliation addressed.

### IR-12: API contract and ownership (line 31) [R, C]
`resolve` returns `(status, location)`; no statement whether the signature changes or the web layer passes new inputs (client IP, user agent). No owner identification or authorization for reading counts; no read API is planned though the Objective requires owners to see counts.

### IR-13: Step wording inconsistent with design vocabulary (lines 30-33) [T]
Steps are fragments with uneven specificity. Use one pattern, for example "Add `shortener/counter.py` with `increment(slug)` and `get_count(slug)`." (This is a pattern example for the resolver to adapt; the module name is illustrative.)

## 🟢 Nit

### IR-14: No per-step acceptance criteria; `MAX_SLUG_LEN` and the `put` `ValueError` not mentioned (lines 12-14, 30-33) [R, C]
### IR-15: "CEP" is an undefined acronym at line 23 (outside range, affects step coverage) [T]

**Counts (deduplicated):** Blocker 9, Major 4, Nit 2.
