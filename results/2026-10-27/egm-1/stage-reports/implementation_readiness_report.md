# Implementation Readiness Test: Click Analytics (Stage 9)

Target: `docs/designs/click_analytics.md`, DetailedRange lines 28..34. Reviewers: `egm-implementation-readiness`, `egm-codebase-details`, `egm-style` (deduplicated). Standard: `implementation-readiness-standard`.

**Verdict: fails.** An implementer would have to make every design decision.

## 🔴 Blocker

1. **Plan has no actionable content (lines 30–33).** No files created, modified or deleted. No function names, signatures, DDL, driver, config or credentials. "Update the API" does not say what changes in `resolve` (`api.py:14-19`) or how the counter is injected. "Ship it" is not a step.
2. **Increment is unsafe (lines 19–21, step 2).** Read-then-write loses clicks. `README.md:2` says the web layer runs 4 gunicorn workers, so races happen across processes. Specify an atomic upsert (`INSERT ... ON CONFLICT (slug) DO UPDATE SET count = count + 1`). No table, schema, migration or owner is defined.
3. **No failure policy for the synchronous Postgres write.** No timeout, and no decision on whether the redirect fails or the error is swallowed. This is a core decision left to the implementer.
4. **CEP forwarding has no plan step (line 23).** It lacks transport, schema, auth, delivery semantics and failure handling, and "CEP" is undefined. Add a step or cut it.
5. **Bot detection is undefined (line 32, lines 25–26).** No interface, module path, inputs, outputs, or effect on counting. It conflicts with "in the future". Cut it or fully specify it.
6. **No phasing or checkpoints.** "Phase 1" is never defined. There is no feature flag, rollback, or ordering for deploying the table before the code.
7. **No test plan.** Required cases: 302 increments, 404 does not, concurrent resolves count correctly, a backend failure still redirects, CEP is called once per click, and the bot interface is exercised. The repo has only `tests/test_slugs.py`.
8. **Background contradicts the code (lines 13–14).** `get_url` does not exist (`store.py:16` defines `get`, called at `api.py:16`). Slugs use SHA-256 (`slugs.py:9-10`), not MD5. Code written from the doc would call a nonexistent method.

## 🟡 Major

9. **Request metadata is missing.** `resolve` takes only `slug`. Bot detection and CEP events need user agent, IP or timestamp. That means a signature change and a change to the web layer, which is outside this repo and is a cross-team dependency. The click event contents are not defined.
10. **Slug constraints.** `store.put` rejects slugs longer than `MAX_SLUG_LEN = 16` (`store.py:4, 12-13`), and the counter key needs a matching constraint. `make_slug` truncates to 7 base62 characters, and `put` silently overwrites on collision, which would merge counts.
11. **No read path (line 8).** Nothing exposes counts to owners, and the code has no owner concept.
12. **Data consistency.** `LinkStore` is an in-process dict (`store.py:9`) and links vanish on restart, while Postgres counts persist. Per-worker state also differs across the 4 workers. No retention policy is stated.
13. **Missing test infrastructure.** There are no fakes for Postgres or CEP. Reuse the `LinkStore` interface pattern (`store.py:7-17`) for an in-memory `CounterStore` fake. Everything else is greenfield, and the plan should say so.
14. **Scope.** The bot framework has no consumer or codebase pattern. Move it to a separate design.
15. **Vague step wording.** Steps 1–2 do not say which files or behavior change, and step 3 uses "plugin interface" and "framework" for the same item.

## 🟢 Nit

16. Steps should name the objects they change (e.g. `shortener/counter.py` with `class ClickCounter`) and map to phases.
17. Each step should state a verifiable outcome.
18. "CEP" is never defined.
