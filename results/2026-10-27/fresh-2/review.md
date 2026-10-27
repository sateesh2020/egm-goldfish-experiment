# Review: docs/designs/click_analytics.md

Reviewed against the code at commit `7409751`.

## Blocker

1. **Read-modify-write counter loses clicks (Design, para 1).** The design says the increment "reads the current count and writes back `count + 1`". The README says the web layer runs `resolve` under 4 gunicorn worker processes, so concurrent clicks on the same slug will read the same value and overwrite each other. Counts will be systematically undercounted on hot links. Use an atomic `UPDATE ... SET count = count + 1` / `INSERT ... ON CONFLICT DO UPDATE`, or append events and aggregate.

2. **Synchronous write to an external Postgres on the redirect path (Design, para 1).** The increment happens "before it returns the redirect". `resolve` is currently a pure in-memory lookup. The design makes every redirect depend on the latency and availability of a database owned by another team, and says nothing about timeouts or failure behavior. An analytics outage would take down redirects. The count should be recorded asynchronously (queue or buffer), and failures must never fail or delay the 302.

3. **Background cites code that does not exist.** `LinkStore.get_url(slug)` is not in `shortener/store.py`. The method is `LinkStore.get(slug)`. The design's hook point is therefore described inaccurately, and the plan cannot be implemented as written without clarification.

4. **"Slugs are generated with MD5" is wrong.** `shortener/slugs.py` uses SHA-256. The design rests on an inaccurate description of the code. It also never discusses that slugs are deterministic per URL (see Major 2).

## Major

1. **Undefined "CEP" (Design, para 2).** "CEP" is never expanded or linked. Nothing in the repo refers to it. There is no event schema, transport, delivery guarantee, ownership, or failure handling. Forwarding events is also not required by the Objective. It sends user click data to other teams with no privacy or PII discussion (IP, user agent, referrer).

2. **Deterministic slugs mean one counter per URL, not per link owner.** `make_slug` derives the slug only from the URL, so two owners who shorten the same URL get the same slug. The Objective says "show link owners how many times each short link was clicked". The code has no concept of an owner, and `create_link` takes no user. The design needs an ownership model, authentication, and an API to read counts. It describes only the write side.

3. **No read path.** Nothing says how owners see counts: no endpoint, no `get_clicks` handler, no auth or response shape. The Objective is not met by the design as written.

4. **Scope creep: ML bot detection (Design, para 3).** A "pluggable, ML-based bot-detection framework" is not needed for the stated objective. It is speculative ("in the future"), has no requirements, and is a large, unspecified piece of work. Remove it from Phase 1 or move it to a separate design. If bot filtering matters, store the raw user agent so it can be done later.

5. **Implementation plan is not actionable.** The four steps ("Add a counter module", "Update the API", "Ship it") have no detail on schema, migrations, files touched, tests, rollout, or rollback. "Phase 1" is mentioned but no other phases are defined.

6. **Missing requirements and decisions.** No stated expectations for accuracy (exact vs. approximate), latency budget, expected traffic, retention, or count semantics. It does not say whether 404s count (the design says only "succeeds"), or whether repeated or bot clicks count.

7. **Cross-process and testing concerns.** `store` is an in-process `LinkStore`, so each of the 4 workers has its own copy of the links. This is an existing problem, but the design adds shared state (the counter) without noticing that link state is not shared. Link-existence checks in `resolve` can disagree between workers. There are no tests planned. The repo has only slug tests, and `resolve` has no tests.

## Nit

1. Author is "example" and the status is Draft, with no reviewers or dates.
2. The Objective is one line with no success metrics.
3. The step numbering in the plan lists the "bot-detection plugin interface" after "Update the API" but the design does not say how it would hook into `resolve`.
4. Names are used inconsistently ("click count", "click event"). The counter module name and table schema are not given.
5. The Background mentions `create_link` but the design never says whether creation initializes a counter row.
