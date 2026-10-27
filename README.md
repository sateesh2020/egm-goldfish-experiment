# egm-goldfish-experiment

A small, reproducible test of Google's [Elephant-Goldfish Model (EGM)](https://github.com/google/elephant-goldfish-model): does reviewing an AI-written design doc with zero-context "Goldfish" subagents catch more than a plain review?

This repo is the companion to the article *[The Agent That Wrote Your Spec Shouldn't Be the One Reviewing It](#article)*. It contains the toy codebase, the flawed design doc, the list of planted flaws, the exact prompts, a runner that drives the Claude Code CLI, a scorer, and the raw results of the reference run on 27 October 2026.

> This is an independent experiment. It is not affiliated with Google or with the EGM project.

## What it tests

A three-file Python link shortener (`toy/`) and a short design doc for click analytics (`toy/docs/designs/click_analytics.md`) with **seven flaws planted on purpose**, written down before any review ran ([`experiment/planted_flaws.json`](experiment/planted_flaws.json)):

| ID | Planted flaw |
|---|---|
| F1 | Wrong method name (`get_url`; the code has `get`) |
| F2 | Wrong hash algorithm (MD5; the code uses SHA-256) |
| F3 | Undefined acronym ("the CEP") |
| F4 | Speculative ML bot-detection framework |
| F5 | Synchronous write to another team's Postgres in the redirect path, with no failure behaviour |
| F6 | Read-then-write counter that loses clicks across 4 worker processes |
| F7 | Implementation plan with no files or tests; last step is "Ship it" |

Three kinds of reviewer get the same doc and the same model:

| Arm | What runs |
|---|---|
| `egm` | `/egm:egm-review docs/designs/click_analytics.md uninterrupted`: EGM's five-stage pipeline with isolated reviewer subagents |
| `fresh` | One plain prompt ([`experiment/prompts/review.txt`](experiment/prompts/review.txt)) in a brand-new session. This is itself a zero-context reviewer, just without EGM's stages and rubrics. |
| `in-context` | Turn 1 gives the author's reasons and asks the model to save the doc ([`in_context_turn1.txt`](experiment/prompts/in_context_turn1.txt)). Turn 2, in the same session, sends the same review prompt. This approximates the self-review EGM warns about. |

## Results of the reference run (27 Oct 2026)

Claude Code 2.1.311, headless, CLI default model (`claude-sonnet-5-5`), EGM at commit [`b3a3595`](https://github.com/google/elephant-goldfish-model/commit/b3a3595), plugin v0.1.0.

| Arm | Runs | Planted flaws found | Findings | Time per run | Cost per run* |
|---|---|---|---|---|---|
| EGM `/egm-review` | 1 | 7/7 | 26 action items + 5 stage reports | 185 s (9 reviewer subagents) | $0.88 |
| Fresh-session review | 3 | 7/7, 7/7, 7/7 | 14–16 | 21–25 s | $0.07–0.20 |
| In-context review | 3 | 7/7, 7/7, 7/7 | 14–16 | 38–42 s (both turns) | $0.19–0.21 |

\*As reported by the CLI at API rates. A subscription draws on plan usage instead.

Full output: [`results/2026-10-27/results.md`](results/2026-10-27/results.md). Every review is in `results/2026-10-27/<run>/review.md`. The EGM run also includes its stage reports and full transcripts with paths and account details redacted (`egm-1/transcripts.tgz`, including each subagent's tool calls).

**What we read from it:**

- Every reviewer found every planted flaw. On this doc, a cheap fresh-context review was enough to catch them, and the expected self-review blind spot did not appear. In all three in-context runs, the model pointed out the MD5 and `get_url` errors while it was *saving* the doc.
- EGM's extra cost bought rubric-driven completeness, not more catches. It flagged missing Alternatives, Goals and Non-Goals, Risks, and a rollout plan, and every action item traces back to the stage that raised it.
- The isolation is real. Each EGM reviewer read only its persona, its rubric, the doc and the source files, and none edited anything.

### Re-run with this repo's runner (27 Oct 2026)

After building the runner, we ran it once more (1 run per arm) to check that it reproduces the result: [`results/2026-10-27-rerun/`](results/2026-10-27-rerun/results.md).

| Arm | Planted flaws found | Findings | Time | Cost |
|---|---|---|---|---|
| EGM | 7/7 | 17 action items | 260 s | $1.29 |
| Fresh | 7/7 | 17 | 34 s | $0.13 |
| In-context | 7/7 | 17 | 41 s (both turns) | $0.26 |

Same outcome, with different numbers. EGM's run also shows how much these runs vary. The orchestrator first tried to delegate to its synthesizer subagent, which couldn't spawn reviewers and reviewed the doc itself. EGM then discarded that output and re-ran the stage with a fresh reviewer, as its docs require. That retry is part of why this run took longer and cost more.

**Limits:** one toy doc with deliberately obvious flaws; n=1 (EGM) and n=3 (others); one model; only `/egm-review` was exercised. This is a demonstration, not a benchmark. The interesting next experiment is a real design with subtle, unplanted problems.

## Reproduce it

Requirements: Python 3.10+ (standard library only), the [Claude Code CLI](https://code.claude.com/docs) signed in (EGM's docs require 2.1.271 or later for reviewer isolation), and `git`, which is used to fetch EGM.

```bash
git clone https://github.com/sateesh2020/cd-egm-goldfish-experiment.git && cd cd-egm-goldfish-experiment

# See exactly what will run, without calling anything
python3 scripts/run_experiment.py --dry-run

# Cheapest real check: one fresh review (~25 s, about $0.10)
python3 scripts/run_experiment.py --arms fresh --runs 1

# The full experiment: 1 EGM run + 3 fresh + 3 in-context (~$2 at API rates)
python3 scripts/run_experiment.py --parallel 3
```

Results land in `results/<UTC timestamp>/`, one folder per run, with `review.md`, the CLI's `result*.json`, `run.json` (the exact commands), `manifest.json` and a scored `results.md`.

Useful options:

| Option | Meaning |
|---|---|
| `--arms egm,fresh,in-context` | Pick arms |
| `--runs N` / `--egm-runs N` | Runs per arm |
| `--egm-ref <commit>` | EGM commit to clone into `.cache/` (default `b3a3595`) |
| `--egm-plugin-dir PATH` | Use a local EGM checkout instead |
| `--model NAME` | Pass a model to `claude` (default: the CLI's default) |
| `--parallel N` | Runs at once |
| `--isolated-home` | Empty `HOME` per call. Use this only when auth comes from environment variables, or `claude` won't be signed in. |

**Before you commit or share results**, sanitize them. Claude Code's result files and transcripts can include local paths and account context, such as your email address:

```bash
python3 scripts/sanitize_results.py results/<run-folder>          # rewrite in place
python3 scripts/sanitize_results.py results --check               # verify (exit 1 if anything left)
```

It keeps only the result fields the scorer needs, redacts emails and absolute paths (including inside `transcripts.tgz`), and removes the per-run `workspace/` copies. The committed results were produced this way, and a test checks that they stay clean.

Re-score any run folder (for example after editing the patterns):

```bash
python3 scripts/score.py results/2026-10-27
```

### How each call is isolated

Every call is headless (`claude -p --output-format json`) with no MCP servers (`--strict-mcp-config --mcp-config '{"mcpServers":{}}'`), project settings only (`--setting-sources project`), and a fixed tool list. Each run works in its own copy of `toy/`. The EGM arm loads the plugin with `--plugin-dir` and writes a project `.claude/settings.json` that allows *read-only* access to the plugin's `agents/`, `docs/`, `resources/` and `skills/` folders. EGM's docs ask you not to disable permission checks, and this runner doesn't. If Claude Code reports that the workspace isn't trusted and ignores those rules, reads may still succeed, as they did in the reference run. If a reviewer reports that it could not read its persona, open the workspace interactively once and accept the trust prompt.

### How scoring works

`score.py` splits each review into findings (paragraph blocks, list items, table rows). A planted flaw counts as found when **one finding** matches every pattern group defined for that flaw. The patterns are deliberately simple, so treat the score as a first pass and read the reviews. The test suite checks that the reference run still scores 7/7 everywhere, and that partial or unrelated reviews do not.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

33 tests, standard library only. The runner tests use a fake `claude` executable, so they make no API calls. They cover command construction, the in-context `--resume` flow, review collection, failure handling, dry runs, and the toy app's real behaviour (it has `get`, not `get_url`, and uses SHA-256).

## Layout

```
toy/                         the codebase under review + the flawed design doc
experiment/planted_flaws.json   the seven flaws and their scoring patterns
experiment/prompts/          review prompt and the in-context setup turn
scripts/run_experiment.py    drives the Claude Code CLI for each arm
scripts/score.py             scores reviews, writes results.md / scores.json
scripts/sanitize_results.py  strips paths, emails and noise from a results folder before you publish it
results/2026-10-27/          the reference run: reviews, CLI results, EGM stage reports and transcripts
results/2026-10-27-rerun/    one run per arm with this repo's runner
tests/                       unit tests (no API calls)
```

## Article

Written for Satheesh Valluru's blog ([medium.com/@satvallu](https://medium.com/@satvallu)). The link will be added here once it's published.

## License

Apache 2.0. See [LICENSE](LICENSE). EGM itself is a separate Apache-2.0 project by Google. It isn't vendored here; the runner clones it at a pinned commit.
