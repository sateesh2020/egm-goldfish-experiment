# Results

| Arm | Runs | Planted flaws found | Findings | Time | Cost (CLI-reported) |
|---|---|---|---|---|---|
| EGM `/egm-review` | 1 | 7/7 | 26 | 185 s | $0.88 |
| Fresh-session review | 3 | 7/7, 7/7, 7/7 | 14–16 | 21 s–25 s | $0.07–$0.20 |
| In-context (same-session) review | 3 | 7/7, 7/7, 7/7 | 14–16 | 38 s–42 s | $0.19–$0.21 |

## Per flaw

| Run | F1 | F2 | F3 | F4 | F5 | F6 | F7 |
|---|---|---|---|---|---|---|---|
| egm-1 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| fresh-1 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| fresh-2 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| fresh-3 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| in-context-1 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| in-context-2 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| in-context-3 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

Flaws: F1 Wrong method name; F2 Wrong hash algorithm; F3 Undefined acronym; F4 Speculative ML bot-detection framework; F5 Remote write on the redirect path with no failure behaviour; F6 Read-then-write counter loses updates; F7 Plan is not actionable.

Scoring is automated pattern matching (see experiment/planted_flaws.json). Read the reviews before you quote a number.

Models seen in usage: claude-haiku-5-5, claude-sonnet-5-5.

Median cost per run: egm $0.88, fresh $0.08, in-context $0.19.
