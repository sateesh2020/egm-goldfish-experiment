#!/usr/bin/env python3
"""Make a results folder safe to publish.

Claude Code's JSON results and transcripts can contain local paths and account
context (for example your email address, attached by the CLI). Run this before
you commit or share a results folder:

    python3 scripts/sanitize_results.py results/<run-folder> [--check]

It rewrites, in place:
  * result*.json   -> only the fields the scorer and readers need
  * all text files  -> email addresses and absolute paths redacted
  * *.tgz           -> the same redaction inside the archive
  * workspace/      -> removed (it's a copy of toy/ plus the reports already collected)

--check makes no changes and exits 1 if anything would be redacted.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import shutil
import sys
import tarfile
from pathlib import Path

KEEP_RESULT_FIELDS = ["type", "subtype", "is_error", "result", "session_id", "duration_ms",
                      "duration_api_ms", "num_turns", "total_cost_usd", "usage", "modelUsage",
                      "permission_denials", "stop_reason", "subagent_stats"]
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
ALLOWED_EMAILS = {"noreply@anthropic.com", "experiment@example.invalid"}
# absolute paths outside the repo: /tmp/..., /home/<user>/..., /Users/<user>/..., /root/...
ABS_PATH = re.compile(r"(?<![\w.])/(?:tmp|private/tmp|var/folders|home|Users|root)/[^\s\"'`)\]<>|]*")
TEXT_SUFFIXES = {".md", ".json", ".jsonl", ".txt", ".yaml", ".yml"}


def redact(text: str) -> tuple[str, int]:
    n = 0

    def email(m: re.Match) -> str:
        nonlocal n
        if m.group(0).lower() in ALLOWED_EMAILS:
            return m.group(0)
        n += 1
        return "<redacted-email>"

    def path(m: re.Match) -> str:
        nonlocal n
        n += 1
        p = m.group(0)
        if "/workspace" in p:  # keep the part inside the run's workspace, e.g. <workspace>/review.md
            return "<workspace>" + p.split("/workspace", 1)[1]
        return "<local-path>/" + p.rstrip("/").rsplit("/", 1)[-1]

    text = EMAIL.sub(email, text)
    text = ABS_PATH.sub(path, text)
    return text, n


def slim_result(text: str) -> str:
    try:
        d = json.loads(text)
    except json.JSONDecodeError:
        return text
    if not isinstance(d, dict):
        return text
    return json.dumps({k: d[k] for k in KEEP_RESULT_FIELDS if k in d}, indent=2)


def sanitize_tgz(path: Path, check: bool) -> int:
    total = 0
    out = io.BytesIO()
    with tarfile.open(path, "r:gz") as src, tarfile.open(fileobj=out, mode="w:gz") as dst:
        for member in src.getmembers():
            data = src.extractfile(member).read() if member.isfile() else None
            if data is not None and Path(member.name).suffix in TEXT_SUFFIXES:
                text, n = redact(data.decode("utf-8", errors="replace"))
                total += n
                data = text.encode("utf-8")
                member.size = len(data)
            dst.addfile(member, io.BytesIO(data) if data is not None else None)
    if total and not check:
        path.write_bytes(out.getvalue())
    return total


def sanitize(root: Path, check: bool = False) -> int:
    total = 0
    for ws in sorted(root.rglob("workspace")):
        if ws.is_dir():
            total += 1
            if not check:
                shutil.rmtree(ws)
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if p.suffixes[-2:] == [".tar", ".gz"] or p.suffix == ".tgz":
            n = sanitize_tgz(p, check)
        elif p.suffix in TEXT_SUFFIXES:
            original = p.read_text(encoding="utf-8", errors="replace")
            text = slim_result(original) if p.name.startswith("result") and p.suffix == ".json" else original
            text, n = redact(text)
            n += int(text != original and n == 0)  # slimming counts as a change
            if text != original and not check:
                p.write_text(text, encoding="utf-8")
        else:
            continue
        if n:
            print(f"{'would change' if check else 'sanitized'}: {p} ({n})")
        total += n
    return total


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", type=Path)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    n = sanitize(args.folder, args.check)
    print(f"{n} change(s){' needed' if args.check else ''}")
    return 1 if (args.check and n) else 0


if __name__ == "__main__":
    sys.exit(main())
