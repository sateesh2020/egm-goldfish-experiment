# Results

| Arm | Runs | Planted flaws found | Findings | Time | Cost (CLI-reported) |
|---|---|---|---|---|---|
| EGM `/egm-review` | 1 | 7/7 | 17 | 260 s | $1.29 |
| Fresh-session review | 1 | 7/7 | 17 | 34 s | $0.13 |
| In-context (same-session) review | 1 | 7/7 | 17 | 41 s | $0.26 |

## Per flaw

| Run | F1 | F2 | F3 | F4 | F5 | F6 | F7 |
|---|---|---|---|---|---|---|---|
| egm-1 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| fresh-1 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| in-context-1 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

Flaws: F1 Wrong method name; F2 Wrong hash algorithm; F3 Undefined acronym; F4 Speculative ML bot-detection framework; F5 Remote write on the redirect path with no failure behaviour; F6 Read-then-write counter loses updates; F7 Plan is not actionable.

Scoring is automated pattern matching (see experiment/planted_flaws.json). Read the reviews before you quote a number.

Models seen in usage: claude-haiku-5-5, claude-sonnet-5-5.

Median cost per run: egm $1.29, fresh $0.13, in-context $0.26.
