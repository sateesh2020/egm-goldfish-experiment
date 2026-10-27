# Consolidated Review Report

**Target:** `docs/designs/click_analytics.md` (33 lines). FeatureRange 1-27, DetailedRange 28-33 (boundary header `## Detailed Implementation Plan` at line 28).
**Mode:** Uninterrupted full flow. The document was not edited during review, so all stages saw the same text.
**Dispatch:** Each stage ran fresh `egm:*` reviewers dispatched directly from the main context. The synthesizer was tried first for Stage 5 but could not spawn a reviewer and reviewed the document itself; that output was discarded and Stage 5 was re-run with a fresh reviewer.
**Stage reports:** `zoom_out_report.md`, `comprehension_report.md`, `critic_report.md`, `intermediate_zoom_out_report.md`, `implementation_readiness_report.md`.

**Verdict:** Not ready to implement. The design has a correctness defect, factual errors about the code, speculative scope, and a plan with no implementable content.

## Actions by priority

### 🔴 Blockers

**A1. Make the increment atomic.** Replace "read current count, write `count + 1`" with an atomic upsert (`INSERT ... ON CONFLICT DO UPDATE SET count = count + 1`). Current text loses clicks under 4 gunicorn workers. Specify first-click behavior.
Sources: ZO-1, CT-4, CR-2, IR-2.

**A2. Define the failure policy for the redirect path.** State that a failed or timed-out count write is logged and swallowed and `resolve` still returns 302, give a timeout, and do not add a queue without measurements. Count only on 302, never on 404.
Sources: ZO-3, CT-5, CT-10, CR-3, CR-15, IR-3, intermediate #2.

**A3. Remove CEP forwarding and ML bot detection from scope; add Goals & Non-Goals.** Neither serves the stated objective, both lack any specification, and plan step 3 contradicts "in the future". "Phase 1" is undefined. If kept, each needs a full spec (CEP: transport, schema, delivery, failure, privacy; bot detection: minimal stub with no-op default).
Sources: ZO-4, ZO-5, CT-7, CT-8, CR-5, CR-8, CR-9, IR-5, IR-6.

**A4. Add an Alternatives Considered section and a stated simplest design.** Compare per-event atomic `UPDATE`, async/batched, Redis `INCR`, event log. Justify the data team's Postgres over a store beside `LinkStore`.
Sources: CR-1, ZO-6, intermediate #3.

**A5. Close the objective: read path, definition of "clicked", ownership.** The design only writes counts. Decide total vs unique, lifetime vs windowed, bots, where counts are shown, who "link owners" are (the code has no owner concept; `make_slug` is deterministic so owners creating the same URL share a slug).
Sources: ZO-6, CT-9, CR-6, CR-10, IR-12, intermediate #5.

**A6. Correct the Background.** SHA-256 not MD5 (`slugs.py:9-10`); `LinkStore.get` not `get_url` (`store.py:16`, `api.py:16`). Do not apply the style reviewer's wording that cites `get_url`.
Sources: ZO-2, CT-2, CT-3, CR-7, IR-4.

**A7. Add a Risks & Mitigations section.** Cover data team SLA and ownership, connection pooling, credentials, failure modes, collisions, privacy if any events are forwarded.
Sources: CR-4, intermediate #11.

**A8. Rewrite the Implementation Plan.** Provide a file list (create/modify), the counter interface and function signatures, one-table schema and DDL with owner of the migration, DB driver dependency and config (no dependency manifest exists), injection of the counter into `resolve`, phases with end-state of each, a rollout/rollback step in place of "Ship it", and a test matrix (increment, 404, concurrency, DB down, no-op/fake counter) naming files in the existing `tests/` directory.
Sources: CT-1, ZO-7, CR-11, CR-13, IR-1, IR-3, IR-7, IR-8, IR-9, intermediate #9-10.

### 🟡 Majors

**A9. State the slug-keyed counter identity and collision behavior.** Counts are per distinct URL, not per owner; 7-char truncation can collide and `put` silently overwrites (`store.py:14`). Accept explicitly or raise as a product decision.
Sources: CR-10, IR-10, intermediate #7.

**A10. State the dependency on an ephemeral store.** `LinkStore` is an in-process dict and each worker has its own copy, so counts can outlive or diverge from links. Record as a dependency or open question. Raise the per-worker link visibility problem separately.
Sources: Stage 5 out-of-scope note, IR-11, intermediate #8.

**A11. Add capacity and accuracy requirements, or record them as open questions.** Latency budget, peak redirect and hot-key rate, accuracy and freshness, access control for who sees counts.
Sources: CR-12, intermediate #11.

**A12. Name the counter component and say how it is mocked.** Interface with Postgres and no-op/in-memory implementations, injected like the module-global `store` (`api.py:5`).
Sources: ZO-8, CT-11, CR-13, IR-3.

**A13. Make plan wording consistent.** One term for each concept; one pattern for steps.
Sources: IR-13.

### 🟢 Nits

**A14.** Replace the placeholder author "example"; add date and reviewers (ZO-9, CT-12, CR-14).
**A15.** Split the Background run-on, state the data team as a dependency, add links, drop the MD5 sentence unless relevant (CR-16).
**A16.** Add an Open Questions / References section (CR-17).
**A17.** Mention `MAX_SLUG_LEN = 16` and `put` `ValueError` only if the counter keys on slug length; define the acronym CEP if it stays (CT-13, IR-14, IR-15).

## Traceability Matrix

| Action | Zoom-out (5) | Comprehension (6) | Critic (7) | Zoom-out (8) | Readiness (9) |
|---|---|---|---|---|---|
| A1 | ZO-1 | CT-4 | CR-2 | #1 | IR-2 |
| A2 | ZO-3 | CT-5, CT-10 | CR-3, CR-15 | #2 | IR-3 |
| A3 | ZO-4, ZO-5 | CT-7, CT-8 | CR-5, CR-8, CR-9 | #4 | IR-5, IR-6 |
| A4 | ZO-6 | | CR-1 | #3 | |
| A5 | ZO-6 | CT-9 | CR-6, CR-10 | #5 | IR-12 |
| A6 | ZO-2 | CT-2, CT-3 | CR-7 | #6 | IR-4 |
| A7 | | | CR-4 | #11 | |
| A8 | ZO-7 | CT-1 | CR-11, CR-13 | #9, #10 | IR-1, IR-3, IR-7, IR-8, IR-9 |
| A9 | | | CR-10 | #7 | IR-10 |
| A10 | out-of-scope note | | | #8 | IR-11 |
| A11 | | CT-14 | CR-12 | #11 | |
| A12 | ZO-8 | CT-11 | CR-13 | #9 | IR-3 |
| A13 | | | | | IR-13 |
| A14 | ZO-9 | CT-12 | CR-14 | #12 | |
| A15 | | | CR-16 | #13 | |
| A16 | | | CR-17 | #11 | |
| A17 | | CT-13 | | | IR-14, IR-15 |

## Totals by stage (as reported in each stage file)

| Stage | Blocker | Major | Nit |
|---|---|---|---|
| 5 Zoom Out | 1 | 6 | 2 |
| 6 Comprehension | 5 | 6 | 3 |
| 7 Critic | 6 | 7 | 4 |
| 8 Intermediate Zoom Out | 5 | 6 | 2 |
| 9 Implementation Readiness | 9 | 4 | 2 |

Consolidated: 8 Blocker actions, 5 Major actions, 4 Nit actions.

## Reviewer disagreements and corrections recorded

* Stage 9: the readiness reviewer said no `tests/` directory exists; the codebase reviewer found `tests/test_slugs.py`. Verified by glob: the directory and file exist; no dependency manifest or test-runner config exists.
* Severity of the thin Problem Statement and the bot-detection step differed between lenses; the higher severity is reported in each stage file with the split noted.
* Stage 7 style Nit 5 suggested `LinkStore.get_url(slug)`, repeating the Background error. Flagged in CR-7.

## Not done

No fixes were applied to the design document (uninterrupted mode reports only). Resolution can be run with `egm-resolve` on this report.
