# Critic Review: Click Analytics (Stage 7)

Target: `docs/designs/click_analytics.md`, FeatureRange lines 1..27. Reviewers: `egm-design`, `egm-structural`, `egm-style` (deduplicated). Standard: `feature-spec-standard`. The design reviewer reported that `agents/design.md` does not exist and used `agents/design_critic.md`.

## 🔴 Blocker

1. **No Alternatives Considered section (whole doc).** Single path, no rejected options (async or batched counting, log or stream aggregation, Redis `INCR`, sampling, deriving counts from CEP). *(design, structural)*
2. **Synchronous, racy increment (lines 18–21).** Read-then-write loses concurrent clicks. A synchronous write to another team's Postgres sits in the redirect path, with no timeout, fail-open behavior, or load estimate. Hot slugs are a lock-contention point. Use an atomic update, take it off the redirect path, and define failure behavior. *(design, style)*
3. **No Risks & Mitigations section (lines 16–26).** Nothing on failure modes, abuse (count inflation, unauthenticated reads), scalability, cost, data-team agreement, schema, rollout or rollback. *(design, structural)*
4. **No Goals/Non-Goals, success metrics or accuracy requirement (lines 6–8, 25–26).** Unclear whether counts are exact or approximate, total or unique, how fresh, and where owners see them. No read path is specified. *(design, structural, style)*
5. **Bot-detection framework is scope creep (lines 25–26).** Speculative ("in the future"), no evidence of a bot problem, no owner or model. "Phase 1" is undefined. Cut it to future work or justify it. *(design, structural, style)*

## 🟡 Major

6. **CEP forwarding (lines 23–24).** "CEP" is undefined. No event schema, delivery semantics, failure handling, named consumer, or privacy and retention analysis. *(design, structural, style)*
7. **Background contradicts the code (lines 12–14).** Slugs use SHA-256 (`slugs.py:9`), not MD5. The method is `LinkStore.get` (`store.py:16`), not `get_url`. *(design)*
8. **Link identity and ownership (line 8).** Slugs are deterministic per URL, so owners shortening the same URL share one count. There is no owner concept in the code. The 7-character truncation risks collisions, and `put` overwrites silently, which would corrupt counts. *(design)*
9. **Counting semantics (lines 18–19).** The doc does not say 404s are excluded. It does not cover prefetchers, crawlers, HEAD requests or replays. The in-process `LinkStore` diverges from Postgres counts across multiple instances. *(design)*
10. **Design is unstructured (lines 16–26).** Three concerns (counting, CEP, bots) share three paragraphs with no subsections, data flow or component layout. *(structural)*
11. **"Objective" is a stakeholder wish, not a Problem Statement (lines 6–8).** Rename it, add the user problem and a measurable boundary. *(structural, style)*
12. **Bot-detection wording is vague (lines 25–26).** "Pluggable", "framework" and "ML-based" name nothing concrete, and "in the future" conflicts with "Phase 1 also adds". *(style)*
13. **Plan is non-actionable (lines 28–33; outside FeatureRange).** "Ship it" is not a step, and there is no test plan. *(design)*

## 🟢 Nit

14. Lines 3–4: placeholder author, no date or reviewers.
15. Lines 12–14: code references have no links or anchors.
16. Lines 18–20: wording ("When `resolve` succeeds, it", "live in", the two-fact parenthetical, "also").
17. Lines 20–21: state the operation exactly, e.g. "read-then-write".
