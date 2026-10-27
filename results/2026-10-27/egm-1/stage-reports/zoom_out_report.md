# Zoom Out Review: Click Analytics for Short Links (Stage 5, Initial)

Target: `docs/designs/click_analytics.md`, lines 1–34. Reviewer: `egm:egm-zoom-out`. No extra Goldfish context was provided.

## 🔴 Blocker

1. **Bot-detection framework (lines 25–26, plan step 3, line 32): YAGNI.** The objective does not ask for bot filtering, and the doc says "in the future". Remove it from Phase 1, or state bot traffic as a requirement with evidence.
2. **Read-then-write increment (lines 20–21): lost-update race.** Concurrent clicks undercount. State the accuracy requirement and use an atomic increment or upsert.
3. **Synchronous external writes in the redirect path (lines 18–19, 23).** `resolve` is currently an in-memory lookup (`api.py:14-19`). A Postgres write owned by another team plus a CEP forward before every redirect means an analytics outage can break or slow redirects. No failure policy is given. Analytics must not fail the redirect.

## 🟡 Major

4. **CEP forwarding (line 23).** "CEP" is never defined, and there is no named consumer, contract or owner. Drop it, or define the contract and owner.
5. **Background contradicts the code (lines 12–14).** `slugs.py:9-10` uses SHA-256, not MD5. The method is `LinkStore.get` (`store.py:16`), not `get_url`.
6. **Storage mismatch (lines 19–20).** The system is a single-process in-memory dict. A cross-team Postgres dependency is stated as fact, with no justification or alternatives. The in-memory store loses links on restart, so durable counts can outlive their links.
7. **No read path (line 8).** The goal is to show counts to link owners. The design only writes counts, has no read accessor, and the code has no owner concept.
8. **Placement (lines 18, 30–31).** Put a narrow `record_click(slug)` interface behind `resolve` instead of coupling the increment into the handler. Do not build a plugin system.

## 🟢 Nit

9. **Implementation plan (lines 28–33)** names no interfaces, data flow, tests, rollout or rollback.
10. **Missing scope details:** non-goals, success criteria, privacy (IP and user agent), expected click volume.

## Suggested minimal shape

A single `record_click(slug)` call in `resolve`, an atomic increment with failures swallowed and logged, a read accessor for owners, and no CEP or bot framework until requirements exist.
