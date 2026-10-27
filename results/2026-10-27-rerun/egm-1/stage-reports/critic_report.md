# Stage 7: Critic Review Report

**Target:** `docs/designs/click_analytics.md` (FeatureRange 1-27)
**Reviewers:** `egm-design`, `egm-structural`, `egm-style` (fresh Goldfish, direct dispatch), standard `feature-spec-standard` for design and structural.
Findings are deduplicated across reviewers. Lens tags: D = design, S = structural, T = style.

## 🔴 Blocker

### CR-1: No Alternatives Considered section (lines 16-26) [D, S]
A single path is proposed with no rejected options. Candidates to compare: atomic per-event `UPDATE`, async/batched or queued counter, Redis `INCR` with flush, append-only click log aggregated at read time, log-based analytics from the web tier. Compare on cost, latency, correctness, operational burden.

### CR-2: Lost-update race in the increment (lines 18-21) [D, S, T]
"Reads the current count and writes back `count + 1`" loses clicks under concurrency; popular links are hit hardest. Specify an atomic increment (`SET count = count + 1`) or an event log. First-click (no row) behavior is unspecified. (T: wording is also ambiguous and not verifiable as written.)

### CR-3: Synchronous remote write on the redirect path with no failure policy (lines 18-22) [D, S]
Every redirect depends on a Postgres owned by another team. Slowness or outage makes redirects slow or fail. No timeout, fail-open/fail-closed policy or retry is given. Take the write off the request path or define fail-open explicitly.

### CR-4: No Risks & Mitigations section (lines 16-26) [S]
Failure modes, security, scalability limits and privacy (CEP forwarding) go unaddressed. See CR-2, CR-3, CR-8.

### CR-5: No Goals & Non-Goals section (lines 1-27) [D, S]
Required by the standard. Its absence is how CEP forwarding and ML bot detection entered scope.

### CR-6: Problem Statement is a single line with no measurable goal (lines 6-8) [D, S, T]
No user problem, motivation or success measure. "Clicked" is undefined (total vs unique, lifetime vs windowed, bots, 404s), as are where counts are shown and who the "link owners" are. (Severity: Blocker per structural lens; Major per design and style lenses.)

## 🟡 Major

### CR-7: Background contradicts the code (lines 12-14) [D, S]
Slugs use SHA-256 (`slugs.py:9-10`), not MD5. The method is `LinkStore.get(slug)` (`store.py:16`, called at `api.py:16`), not `get_url`.
Note for the resolver: the style lens's Nit 5 suggested wording using `LinkStore.get_url(slug)`; that suggestion repeats the error and must not be applied.

### CR-8: "CEP" forwarding is undefined, out of scope and a privacy risk (line 23) [D, S, T]
No expansion, transport, payload, delivery guarantee, sync/async behavior or failure handling. Dual-write inconsistency with Postgres. Events may carry IP, user agent, referrer with no retention or PII policy. Not tied to the Objective. Specify it or make it a non-goal.

### CR-9: Speculative ML bot-detection framework in "Phase 1" (lines 25-26) [D, S, T]
YAGNI; no requirement, success criteria or model/data ownership; "Phase 1" is never defined; text says "future" while plan step 3 builds it now. False positives would distort customer-facing counts. Remove from Phase 1; if needed, a simple user-agent or rate heuristic plus stored raw events.

### CR-10: Slug and ownership model do not support per-owner counts (lines 18-22) [D]
`make_slug` is deterministic on the URL, so different owners creating the same URL share one slug and counter. No owner is recorded anywhere. `LinkStore` is an in-process dict with no persistence or cross-instance sharing, so counts keyed by slug can be orphaned on restart. 7-char truncation can collide and `put` silently overwrites (`store.py:14`), merging counters of unrelated URLs.

### CR-11: Architecture detail is missing (lines 16-26) [D, S]
Design is unstructured prose with no component layout, data flow, schema, connection/pooling, credentials, cross-team SLA, migration or rollout. No sub-headings separating counting, CEP and bot detection. No read path to owners.

### CR-12: Capacity and accuracy requirements absent (lines 1-27) [D]
No peak redirect QPS or hot-key QPS, write amplification, storage growth, accuracy or freshness requirement, click-inflation abuse handling, or access control for who sees counts.

### CR-13: Remote I/O added to a pure handler without injection or test plan (lines 18-21) [D, S]
`resolve` is HTTP-agnostic with no I/O and a module-level `store` (`api.py:5`). The design does not say how the counter dependency is injected or mocked.

## 🟢 Nit

### CR-14: Placeholder metadata (lines 3-4) [D, S, T]
Author is "example"; no date or reviewers.

### CR-15: "When `resolve` succeeds" is not defined (line 18) [T]
State the exact condition (302 issued; 404 not counted).

### CR-16: Wording and links (lines 12-14, 19-20) [S, T]
Background is a run-on mixing three functions and two files; the MD5 sentence has no stated relevance. "Counts live in" is informal; the data-team ownership aside should be stated as a dependency. File paths and CEP have no links.

### CR-17: No Open Questions or References section [S]
Would hold the unresolved items above.

**Counts (deduplicated):** Blocker 6, Major 7, Nit 4.
