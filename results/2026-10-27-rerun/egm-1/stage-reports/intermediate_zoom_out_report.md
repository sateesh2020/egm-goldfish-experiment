# Stage 8: Intermediate Zoom Out Report

**Target:** `docs/designs/click_analytics.md` (full file, lines 1-33; unchanged since Stage 5)
**Reviewer:** `egm-zoom-out` (fresh Goldfish, direct dispatch)
**Inputs:** `zoom_out_report.md`, `comprehension_report.md`, `critic_report.md`

All Stage 5-7 findings still apply because the document was not edited in uninterrupted mode. Cross-references use ZO-n (Stage 5), CT-n (Stage 6), CR-n (Stage 7).

## 🔴 Blocker

1. **Lost-update increment (lines 18-21)** (ZO-1, CT-4, CR-2). Under 4 gunicorn workers (`README.md:2`) read-then-write undercounts. Require an atomic increment with upsert for the first click.
2. **Synchronous cross-team write, no failure policy (lines 18-20)** (ZO-3, CT-5, CR-3). State fail-open: a failed or timed-out write is logged and swallowed and the redirect still returns 302; state a timeout. No queue without measurements. Raised to Blocker because it makes the core flow depend on another team.
3. **No simplest-viable-design baseline or Alternatives (lines 16-26)** (CR-1, ZO-6). Name one minimal design (per-slug row, atomic increment, fail-open call, read path) and list rejected options (event log, Redis, async queue) in a sentence or two each.
4. **Scope creep remains (lines 23-26, plan step 3)** (ZO-4, ZO-5, CR-5, CR-8, CR-9). Remove CEP forwarding and ML bot detection; add Non-Goals. Line 26 says "future" while plan step 3 builds it; "Phase 1" is undefined.
5. **Read path absent, so the Objective is not met (lines 6-8, 16-26)** (ZO-6, CT-9). Decide: total clicks per slug via a simple lookup with ownership/auth out of scope, or add ownership. `create_link` has no owner concept (`api.py:8`).

## 🟡 Major

6. **Background is factually wrong (lines 12-14)** (ZO-2, CT-2, CT-3, CR-7). SHA-256, not MD5; `get`, not `get_url`.
7. **Slug-keyed counter identity (lines 18-22)** (CR-10). Slugs are deterministic per URL, so counts are per distinct URL, not per owner. 7-char truncation can collide and `put` overwrites silently (`store.py:14`). State this or flag it as a product decision.
8. **Counts keyed to an ephemeral store.** `LinkStore` is an in-process dict, so each worker has its own links; Postgres counts could outlive or diverge from links. State as a dependency or open question.
9. **Counter wiring and placement unspecified (lines 18-19, 28-33)** (CR-13, CT-11, ZO-8). Counter as an interface with Postgres and no-op/in-memory implementations; count only on 302, never on 404 (CR-15).
10. **Implementation plan not actionable (lines 28-33)** (CT-1, ZO-7). Architecture-level list: counter interface, one-table schema, fail-open call in `resolve`, tests (concurrency, database-down), rollout/verification. No pseudocode.
11. **Required sections missing** (CR-4, CR-5, CR-6, CR-12, CR-17). Goals/Non-Goals, Risks & Mitigations (data team SLA, pooling, credentials), Open Questions (definition of "clicked"), and at least a latency budget and peak hot-key rate or open questions for them.

## 🟢 Nit

12. **Placeholder metadata (lines 3-4)** (ZO-9, CT-12, CR-14).
13. **Wording (lines 12-14, 19-20)** (CR-16).

## Reuse check
No counter, database client, analytics or event code exists in the workspace. Keep `resolve` as the single call site.

## Simplest viable design the document should state
Per-slug counter with atomic upsert increment; fail-open, timeout-bounded call from `resolve` after a 302; a simple read path; CEP and bot detection listed as non-goals.

**Counts:** Blocker 5, Major 6, Nit 2.
