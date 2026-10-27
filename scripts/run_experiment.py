#!/usr/bin/env python3
"""Run the planted-flaw review experiment with the Claude Code CLI.

Three arms review the same flawed design doc (toy/docs/designs/click_analytics.md):

  egm         Google's Elephant-Goldfish Model: /egm:egm-review ... uninterrupted
  fresh       one plain review prompt in a brand-new session
  in-context  the same session first hears the author's reasons and saves the doc,
              then gets the same review prompt (approximates self-review)

Each run gets its own copy of toy/ under OUT/<arm>-<n>/workspace. The CLI's JSON
result (time, turns, cost, models) is saved next to the review. Afterwards
scripts/score.py scores every review against experiment/planted_flaws.json.

Examples:
    python3 scripts/run_experiment.py --dry-run
    python3 scripts/run_experiment.py --arms fresh --runs 1
    python3 scripts/run_experiment.py                      # 1 EGM run, 3 fresh, 3 in-context

Runs cost real money (or plan usage). The reference run on 2026-10-27 cost about
$1.90 in total at API rates. Standard library only; needs `claude` (and `git` to
fetch EGM unless you pass --egm-plugin-dir).
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOY = ROOT / "toy"
PROMPTS = ROOT / "experiment" / "prompts"
DOC = "docs/designs/click_analytics.md"
EGM_REPO = "https://github.com/google/elephant-goldfish-model"
EGM_DEFAULT_REF = "b3a3595"  # the commit used for the 2026-10-27 reference run
EGM_COMMAND = f"/egm:egm-review {DOC} uninterrupted"
EGM_REPORT_NAMES = ["consolidated_review_report.md", "goldfish_review_report.md"]
ARMS = ("egm", "fresh", "in-context")
BASE_TOOLS = "Read Grep Glob Write Edit"


@dataclass
class Settings:
    out: Path
    claude: str = "claude"
    model: str | None = None
    timeout: int = 1800
    isolated_home: bool = False
    dry_run: bool = False
    egm_plugin_dir: Path | None = None


@dataclass
class RunResult:
    name: str
    ok: bool
    commands: list[list[str]] = field(default_factory=list)
    note: str = ""


# --------------------------------------------------------------------------- helpers
def base_command(s: Settings, prompt: str, tools: str, extra: list[str] | None = None) -> list[str]:
    """Headless claude call with no MCP servers and project-only settings."""
    cmd = [s.claude, "-p", prompt, "--output-format", "json",
           "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
           "--setting-sources", "project",
           "--permission-mode", "acceptEdits", "--allowedTools", tools]
    if s.model:
        cmd += ["--model", s.model]
    return cmd + (extra or [])


def egm_settings(plugin_dir: Path) -> dict:
    """Project settings that let reviewers read the plugin's personas and rubrics (read-only)."""
    p = plugin_dir.resolve().as_posix()
    rules = [f"Read(/{p}/{d}/**)" for d in ("agents", "docs", "resources", "skills")]
    rules += [f"Glob(/{p}/**)", f"Grep(/{p}/**)"]
    return {"permissions": {"allow": rules}}


def prepare_workspace(run_dir: Path, *, drop_doc: bool = False) -> Path:
    ws = run_dir / "workspace"
    if ws.exists():
        shutil.rmtree(ws)
    shutil.copytree(TOY, ws, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    if drop_doc:
        (ws / DOC).unlink()
    if shutil.which("git"):
        git = ["git", "-c", "user.name=experiment", "-c", "user.email=experiment@example.invalid"]
        subprocess.run(["git", "init", "-q"], cwd=ws, check=True)
        subprocess.run(git + ["add", "-A"], cwd=ws, check=True)
        subprocess.run(git + ["commit", "-qm", "toy repo"], cwd=ws, check=True)
    return ws


def run_claude(cmd: list[str], cwd: Path, out_json: Path, s: Settings, home: Path | None) -> dict:
    if s.dry_run:
        print(f"[dry-run] (cd {cwd} && {' '.join(_q(c) for c in cmd)})")
        return {"session_id": "DRY-RUN", "dry_run": True}
    env = dict(os.environ)
    if home:
        env["HOME"] = str(home)
    proc = subprocess.run(cmd, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, timeout=s.timeout)
    out_json.write_text(proc.stdout, encoding="utf-8")
    if proc.stderr.strip():
        out_json.with_suffix(".stderr.txt").write_text(proc.stderr, encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(f"claude exited {proc.returncode}: {proc.stderr.strip()[:300]}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"claude did not return JSON ({e}); see {out_json}") from e


def _display_path(p: Path) -> str:
    """Repo-relative path when possible, so manifests don't leak local directory names."""
    try:
        return p.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return p.name


def _q(s: str) -> str:
    return s if s and all(c.isalnum() or c in "-_./:=@" for c in s) else "'" + s.replace("'", "'\\''") + "'"


def find_egm_report(ws: Path) -> Path | None:
    for name in EGM_REPORT_NAMES:
        for p in [ws / name, *ws.rglob(name)]:
            if p.exists():
                return p
    reports = sorted(ws.rglob("*report*.md"), key=lambda p: p.stat().st_mtime)
    return reports[-1] if reports else None


def collect_review(run_dir: Path, ws: Path, arm: str, dry: bool) -> bool:
    if dry:
        return True
    if arm == "egm":
        report = find_egm_report(ws)
        stages = run_dir / "stage-reports"
        stages.mkdir(exist_ok=True)
        for p in ws.glob("*_report.md"):
            if report is None or p != report:
                shutil.copy2(p, stages / p.name)
    else:
        report = ws / "review.md"
        if not report.exists():
            report = None
    if report is None:
        return False
    shutil.copy2(report, run_dir / "review.md")
    return True


# --------------------------------------------------------------------------- arms
def run_one(arm: str, index: int, s: Settings) -> RunResult:
    name = f"{arm}-{index}"
    run_dir = s.out / name
    run_dir.mkdir(parents=True, exist_ok=True)
    review_prompt = (PROMPTS / "review.txt").read_text(encoding="utf-8").strip()
    res = RunResult(name, ok=False)
    home_ctx = tempfile.TemporaryDirectory(prefix="egm-exp-home-") if s.isolated_home else None
    home = Path(home_ctx.name) if home_ctx else None
    try:
        if arm == "fresh":
            ws = prepare_workspace(run_dir)
            cmd = base_command(s, review_prompt, BASE_TOOLS)
            res.commands.append(cmd)
            run_claude(cmd, ws, run_dir / "result.json", s, home)
        elif arm == "in-context":
            ws = prepare_workspace(run_dir, drop_doc=True)
            doc = (TOY / DOC).read_text(encoding="utf-8").strip()
            turn1 = (PROMPTS / "in_context_turn1.txt").read_text(encoding="utf-8").replace("{DESIGN_DOC}", doc)
            cmd1 = base_command(s, turn1, BASE_TOOLS)
            res.commands.append(cmd1)
            first = run_claude(cmd1, ws, run_dir / "result-1-setup.json", s, home)
            cmd2 = base_command(s, review_prompt, BASE_TOOLS, ["--resume", first["session_id"]])
            res.commands.append(cmd2)
            run_claude(cmd2, ws, run_dir / "result-2-review.json", s, home)
        elif arm == "egm":
            if s.egm_plugin_dir is None:
                raise RuntimeError("EGM arm needs --egm-plugin-dir or a fetched plugin")
            ws = prepare_workspace(run_dir)
            (ws / ".claude").mkdir(exist_ok=True)
            (ws / ".claude" / "settings.json").write_text(
                json.dumps(egm_settings(s.egm_plugin_dir), indent=2), encoding="utf-8")
            cmd = base_command(s, EGM_COMMAND, BASE_TOOLS + " Agent",
                               ["--plugin-dir", str(s.egm_plugin_dir.resolve())])
            res.commands.append(cmd)
            run_claude(cmd, ws, run_dir / "result.json", s, home)
        else:
            raise ValueError(f"unknown arm {arm}")
        res.ok = collect_review(run_dir, ws, arm, s.dry_run)
        if not res.ok:
            res.note = "no review file was written"
    except Exception as e:  # keep going with the other runs; record what failed
        res.note = str(e)
    finally:
        if home_ctx:
            home_ctx.cleanup()
    (run_dir / "run.json").write_text(json.dumps(
        {"run": name, "ok": res.ok, "note": res.note, "commands": res.commands}, indent=2), encoding="utf-8")
    return res


def fetch_egm(ref: str, cache: Path, dry: bool) -> Path:
    dest = cache / f"elephant-goldfish-model-{ref}"
    if dest.exists():
        return dest
    if dry:
        print(f"[dry-run] git clone {EGM_REPO} {dest} && git -C {dest} checkout {ref}")
        return dest
    if not shutil.which("git"):
        raise SystemExit("git is needed to fetch EGM; or pass --egm-plugin-dir")
    cache.mkdir(parents=True, exist_ok=True)
    tmp = cache / f".tmp-{ref}"
    shutil.rmtree(tmp, ignore_errors=True)
    subprocess.run(["git", "clone", "-q", EGM_REPO, str(tmp)], check=True)
    subprocess.run(["git", "-C", str(tmp), "checkout", "-q", ref], check=True)
    tmp.rename(dest)
    return dest


def claude_version(s: Settings) -> str:
    if s.dry_run:
        return "dry-run"
    try:
        return subprocess.run([s.claude, "--version"], capture_output=True, text=True, timeout=60).stdout.strip()
    except (OSError, subprocess.SubprocessError) as e:
        raise SystemExit(f"could not run '{s.claude} --version': {e}")


def plan_runs(arms: list[str], runs: int, egm_runs: int) -> list[tuple[str, int]]:
    plan = []
    for arm in arms:
        n = egm_runs if arm == "egm" else runs
        plan += [(arm, i) for i in range(1, n + 1)]
    return plan


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arms", default=",".join(ARMS), help="comma list of egm,fresh,in-context")
    ap.add_argument("--runs", type=int, default=3, help="runs per fresh/in-context arm (default 3)")
    ap.add_argument("--egm-runs", type=int, default=1, help="EGM runs (default 1; ~3 min, ~$0.90 each)")
    ap.add_argument("--out", type=Path, help="output folder (default results/<UTC timestamp>)")
    ap.add_argument("--egm-plugin-dir", type=Path, help="local EGM checkout; skips the git clone")
    ap.add_argument("--egm-ref", default=EGM_DEFAULT_REF, help=f"EGM commit to clone (default {EGM_DEFAULT_REF})")
    ap.add_argument("--model", help="pass --model to claude (default: the CLI's default)")
    ap.add_argument("--claude", default="claude", help="claude executable")
    ap.add_argument("--parallel", type=int, default=1, help="runs at once (default 1)")
    ap.add_argument("--timeout", type=int, default=1800, help="seconds per claude call")
    ap.add_argument("--isolated-home", action="store_true",
                    help="run each claude call with an empty HOME (only if auth comes from env vars)")
    ap.add_argument("--dry-run", action="store_true", help="print the commands; call nothing")
    args = ap.parse_args(argv)

    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    bad = [a for a in arms if a not in ARMS]
    if bad:
        ap.error(f"unknown arm(s) {bad}; choose from {list(ARMS)}")
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    out = (args.out or ROOT / "results" / stamp).resolve()
    s = Settings(out=out, claude=args.claude, model=args.model, timeout=args.timeout,
                 isolated_home=args.isolated_home, dry_run=args.dry_run)
    if "egm" in arms:
        s.egm_plugin_dir = (args.egm_plugin_dir.resolve() if args.egm_plugin_dir
                            else fetch_egm(args.egm_ref, ROOT / ".cache", args.dry_run))

    plan = plan_runs(arms, args.runs, args.egm_runs)
    out.mkdir(parents=True, exist_ok=True)
    manifest = {
        "started_utc": stamp, "claude_version": claude_version(s), "model_flag": args.model,
        "egm_plugin_dir": _display_path(s.egm_plugin_dir) if s.egm_plugin_dir else None,
        "egm_ref": None if args.egm_plugin_dir else args.egm_ref,
        "plan": [f"{a}-{i}" for a, i in plan], "dry_run": args.dry_run,
    }
    print(f"{len(plan)} run(s) → {out}")
    with cf.ThreadPoolExecutor(max_workers=max(1, args.parallel)) as pool:
        results = list(pool.map(lambda ai: run_one(ai[0], ai[1], s), plan))
    for r in results:
        print(f"  {'ok ' if r.ok else 'FAIL'} {r.name} {r.note}")
    manifest["finished_utc"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    manifest["runs"] = {r.name: {"ok": r.ok, "note": r.note} for r in results}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    if not args.dry_run and any(r.ok for r in results):
        sys.path.insert(0, str(ROOT / "scripts"))
        import score  # noqa: E402
        score.main([str(out)])
        import build_report  # noqa: E402
        if (ROOT / "results") in out.parents:
            build_report.main([])  # refresh report/index.html with every run set in results/
        else:
            build_report.main([str(out), "--out", str(out / "report.html"), "--no-svg"])
    return 0 if all(r.ok for r in results) else 2


if __name__ == "__main__":
    sys.exit(main())
