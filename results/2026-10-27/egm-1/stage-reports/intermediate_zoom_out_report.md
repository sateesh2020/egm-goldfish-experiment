# Intermediate Zoom Out: Click Analytics (Stage 8)

Target: `docs/designs/click_analytics.md`, lines 1–34. The document is unedited, so all Stage 5 findings still stand. The reviewer did not re-verify the code citations against the code.

**Verdict: still fails.** Nothing was mitigated.

## Escalations

- 🔴 **Plan steps (lines 28–33): Nit to Blocker.** "Ship it" and bare phrases show an absence of architecture, so the plan cannot be used to check simplicity or placement.
- 🔴 **Counter contract (lines 19–21): broader.** No behavior for a slug with no row yet, no schema, DSN source or migration owner, undefined Postgres failure and latency behavior, and a hot-slug lock-contention risk.
- 🔴 **No Alternatives Considered (new).** A simpler path was never weighed: an in-process counter beside `LinkStore`, Redis `INCR`, log aggregation, or counts derived from CEP.
- 🟡 **Problem statement and requirements (lines 6–8): Nit to Major.** There is no accuracy, total-versus-unique, freshness or volume requirement, so proportionality cannot be judged.

## New findings

- 🟡 **Link identity.** Slugs are deterministic per URL, there is no owner concept, and 7-character truncation plus silent overwrite in `put` means the unit being counted is undefined.
- 🟡 **Counting semantics.** The doc is silent on 404s, HEAD requests, prefetchers and crawlers. A simple HEAD or 404 filter may meet the bot need without ML. Multiple instances with an in-process `LinkStore` diverge from the Postgres counts.
- 🟡 **Privacy and abuse.** CEP events may carry IP or user agent with no retention analysis, and unauthenticated counts can be inflated.
- 🟡 **Unstructured design.** `record_click(slug)` should be the single boundary, with CEP and bots deferred behind it.

## Still unmitigated

- 🔴 Bot-detection framework (lines 25–26, step 3).
- 🔴 Synchronous external writes in the redirect path with no fail-open policy.
- 🟡 CEP undefined with no consumer.
- 🟡 Wrong code facts at lines 13–14 (SHA-256 not MD5, `get` not `get_url`).
- 🟡 No read path for owners.
- 🟢 Stage 6 and 7 nits remain valid.

## Recommended direction

Rewrite around an atomic `record_click(slug)` that counts only 302s and logs failures without failing the redirect. Add a read accessor, an accuracy requirement and a measured volume, and an Alternatives section justifying Postgres against an in-process or Redis counter. Defer CEP and bots to named future work. Replace the plan with concrete steps and tests.
