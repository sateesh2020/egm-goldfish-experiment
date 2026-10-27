#!/usr/bin/env python3
"""Score review outputs against the planted-flaws list and build a results table.

Usage:
    python3 scripts/score.py RUN_DIR [--flaws experiment/planted_flaws.json] [--out RUN_DIR]

RUN_DIR holds one sub-folder per run (for example ``egm-1``, ``fresh-2``,
``in-context-3``), each with a ``review.md`` and one or more ``result*.json``
files written by ``claude -p --output-format json``. ``run_experiment.py``
creates this layout.

Writes ``scores.json`` and ``results.md`` to --out (default: RUN_DIR).
Standard library only.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FLAWS = ROOT / "experiment" / "planted_flaws.json"
ARM_ORDER = ["egm", "fresh", "in-context"]
ARM_LABELS = {
    "egm": "EGM `/egm-review`",
    "fresh": "Fresh-session review",
    "in-context": "In-context (same-session) review",
}


# --------------------------------------------------------------------------- findings
def split_findings(text: str) -> list[str]:
    """Split a review into findings: blank-line blocks, list items and table rows."""
    chunks: list[str] = []
    for block in re.split(r"\n\s*\n", text):
        lines = block.strip("\n").splitlines()
        if not lines:
            continue
        if all(l.lstrip().startswith("|") for l in lines):
            chunks.extend(l for l in lines if not re.match(r"^\s*\|[\s:|-]+\|\s*$", l))
            continue
        # split a block of top-level list items (no blank lines between them)
        current: list[str] = []
        for line in lines:
            if re.match(r"^(\d+\.|[-*])\s", line) and current:
                chunks.append("\n".join(current))
                current = []
            current.append(line)
        chunks.append("\n".join(current))
    return [c for c in chunks if c.strip()]


def finding_matches(chunk: str, groups: list[list[str]]) -> bool:
    return all(any(re.search(p, chunk, re.I) for p in group) for group in groups)


def count_findings(text: str) -> int:
    """Count numbered items, severity bullets and ID'd table rows (B1, M2, N3...)."""
    numbered = re.findall(r"^\s{0,3}\d+\.\s+\S", text, re.M)
    table_ids = set(re.findall(r"^\|\s*([BMN]\d+)\s*\|", text, re.M))  # unique: IDs repeat in trace tables
    bold_ids = set(re.findall(r"^\*\*([A-Z]{1,3}\d+)\.", text, re.M))  # "**A1. Title.**" style
    return len(numbered) + len(table_ids) + len(bold_ids)


def score_review(text: str, flaws: list[dict]) -> dict[str, bool]:
    chunks = split_findings(text)
    return {f["id"]: any(finding_matches(c, f["groups"]) for c in chunks) for f in flaws}


# --------------------------------------------------------------------------- runs
def load_usage(run_dir: Path) -> dict:
    """Sum duration, turns and cost over every result*.json in a run folder."""
    total = {"duration_s": 0.0, "turns": 0, "cost_usd": 0.0, "models": set(), "errors": 0}
    files = sorted(run_dir.glob("result*.json"))
    for f in files:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            total["errors"] += 1
            continue
        total["duration_s"] += (d.get("duration_ms") or 0) / 1000
        total["turns"] += d.get("num_turns") or 0
        total["cost_usd"] += d.get("total_cost_usd") or 0.0
        total["models"].update((d.get("modelUsage") or {}).keys())
        if d.get("is_error"):
            total["errors"] += 1
    total["models"] = sorted(total["models"])
    total["result_files"] = len(files)
    return total


def arm_of(name: str) -> str:
    return re.sub(r"-\d+$", "", name)


def score_runs(run_root: Path, flaws: list[dict]) -> list[dict]:
    rows = []
    for d in sorted(p for p in run_root.iterdir() if p.is_dir()):
        review = d / "review.md"
        if not review.exists():
            continue
        text = review.read_text(encoding="utf-8")
        found = score_review(text, flaws)
        rows.append({
            "run": d.name,
            "arm": arm_of(d.name),
            "found": found,
            "found_count": sum(found.values()),
            "findings": count_findings(text),
            **load_usage(d),
        })
    return rows


# --------------------------------------------------------------------------- report
def _range(vals: list[float], fmt: str) -> str:
    if not vals:
        return "n/a"
    lo, hi = min(vals), max(vals)
    return fmt.format(lo) if lo == hi else f"{fmt.format(lo)}–{fmt.format(hi)}"


def render_markdown(rows: list[dict], flaws: list[dict]) -> str:
    n_flaws = len(flaws)
    arms = [a for a in ARM_ORDER if any(r["arm"] == a for r in rows)]
    arms += sorted({r["arm"] for r in rows} - set(arms))
    out = ["# Results", "",
           "| Arm | Runs | Planted flaws found | Findings | Time | Cost (CLI-reported) |",
           "|---|---|---|---|---|---|"]
    for a in arms:
        rs = [r for r in rows if r["arm"] == a]
        found = ", ".join(f"{r['found_count']}/{n_flaws}" for r in rs)
        out.append(
            f"| {ARM_LABELS.get(a, a)} | {len(rs)} | {found} | "
            f"{_range([r['findings'] for r in rs], '{:.0f}')} | "
            f"{_range([r['duration_s'] for r in rs], '{:.0f} s')} | "
            f"{_range([r['cost_usd'] for r in rs], '${:.2f}')} |")
    out += ["", "## Per flaw", "", "| Run | " + " | ".join(f["id"] for f in flaws) + " |",
            "|---|" + "---|" * n_flaws]
    for r in rows:
        out.append(f"| {r['run']} | " + " | ".join("✓" if r["found"][f["id"]] else "✗" for f in flaws) + " |")
    out += ["", "Flaws: " + "; ".join(f"{f['id']} {f['title']}" for f in flaws) + ".", "",
            "Scoring is automated pattern matching (see experiment/planted_flaws.json). "
            "Read the reviews before you quote a number."]
    models = sorted({m for r in rows for m in r["models"]})
    if models:
        out += ["", "Models seen in usage: " + ", ".join(models) + "."]
    if any(r["errors"] for r in rows):
        out += ["", "⚠ Some runs reported errors or unreadable result files: "
                + ", ".join(r["run"] for r in rows if r["errors"]) + "."]
    if len(arms) > 1:
        med = {a: statistics.median([r["cost_usd"] for r in rows if r["arm"] == a]) for a in arms}
        out += ["", "Median cost per run: " + ", ".join(f"{a} ${v:.2f}" for a, v in med.items()) + "."]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--flaws", type=Path, default=DEFAULT_FLAWS)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    flaws = json.loads(args.flaws.read_text(encoding="utf-8"))["flaws"]
    rows = score_runs(args.run_dir, flaws)
    if not rows:
        print(f"no runs with review.md found under {args.run_dir}", file=sys.stderr)
        return 1
    out = args.out or args.run_dir
    out.mkdir(parents=True, exist_ok=True)
    (out / "scores.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    md = render_markdown(rows, flaws)
    (out / "results.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
