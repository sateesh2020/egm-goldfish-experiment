#!/usr/bin/env python3
"""Turn result folders into a visual report.

    python3 scripts/build_report.py                     # every folder under results/
    python3 scripts/build_report.py results/2026-10-27  # just one

Writes:
  report/index.html                 one self-contained page (no network, no build step):
                                    scorecard, cost/time/findings charts, and a review
                                    explorer that highlights where each planted flaw was caught
  results/<run-set>/visuals/*.svg   static charts for the README (GitHub renders them)

Standard library only. Re-run it after scripts/run_experiment.py or after editing
experiment/planted_flaws.json.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import score  # noqa: E402

FLAWS_PATH = ROOT / "experiment" / "planted_flaws.json"
ARM_ORDER = ["egm", "fresh", "in-context"]
ARM_LABEL = {"egm": "EGM /egm-review", "fresh": "Fresh session", "in-context": "In-context"}
# Categorical slots 1-3 of the reference palette (validated all-pairs for 3 series).
ARM_COLOR_LIGHT = {"egm": "#2a78d6", "fresh": "#eb6834", "in-context": "#1baf7a"}
ARM_COLOR_DARK = {"egm": "#3987e5", "fresh": "#d95926", "in-context": "#199e70"}
SEVERITIES = ["Blocker", "Major", "Nit"]
SEV_RE = {"Blocker": re.compile(r"blocker|critical", re.I),
          "Major": re.compile(r"\bmajor", re.I),
          "Nit": re.compile(r"\bnits?\b|\bminor", re.I)}


# =========================================================================== data
@dataclass
class Run:
    name: str
    arm: str
    review: str
    found: dict[str, bool]
    findings: int
    severity: dict[str, int]
    duration_s: float
    turns: int
    cost_usd: float
    models: list[str]
    stage_reports: dict[str, str] = field(default_factory=dict)


@dataclass
class RunSet:
    name: str
    path: Path
    runs: list[Run]
    manifest: dict


def severity_counts(text: str) -> dict[str, int]:
    """Count findings under Blocker / Major / Nit headings (numbered items, ID'd rows, bold IDs)."""
    counts = {s: 0 for s in SEVERITIES}
    current = None
    seen_ids: set[str] = set()
    for line in text.splitlines():
        h = re.match(r"^#{1,6}\s+(.*)", line)
        if h:
            current = next((s for s, rx in SEV_RE.items() if rx.search(h.group(1))), None)
            continue
        if current is None:
            continue
        m_id = re.match(r"^\|\s*([BMN]\d+)\s*\|", line) or re.match(r"^\*\*([A-Z]{1,3}\d+)\.", line)
        if m_id:
            if m_id.group(1) not in seen_ids:
                seen_ids.add(m_id.group(1))
                counts[current] += 1
        elif re.match(r"^\s{0,3}\d+\.\s+\S", line):
            counts[current] += 1
    return counts


def load_runset(path: Path, flaws: list[dict]) -> RunSet:
    runs = []
    for row in score.score_runs(path, flaws):
        d = path / row["run"]
        text = (d / "review.md").read_text(encoding="utf-8")
        stages = {p.stem.replace("_report", "").replace("_", " "): p.read_text(encoding="utf-8")
                  for p in sorted((d / "stage-reports").glob("*.md"))} if (d / "stage-reports").exists() else {}
        runs.append(Run(name=row["run"], arm=row["arm"], review=text, found=row["found"],
                        findings=row["findings"], severity=severity_counts(text),
                        duration_s=row["duration_s"], turns=row["turns"], cost_usd=row["cost_usd"],
                        models=row["models"], stage_reports=stages))
    order = {a: i for i, a in enumerate(ARM_ORDER)}
    runs.sort(key=lambda r: (order.get(r.arm, 99), r.name))
    manifest = {}
    if (path / "manifest.json").exists():
        manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    return RunSet(path.name, path, runs, manifest)


# =========================================================================== markdown
def _inline(s: str) -> str:
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2" rel="noopener">\1</a>', s)
    return s


def _tag(source: str, flaws: list[dict]) -> tuple[str, str]:
    """(attribute, badges) for a finding that matches planted flaws, else ("", "")."""
    hits = [f["id"] for f in flaws if score.finding_matches(source, f["groups"])]
    if not hits:
        return "", ""
    badges = "".join(f'<span class="badge" data-f="{h}">{h}</span>' for h in hits)
    return f' data-flaws="{" ".join(hits)}"', badges


def render_markdown(text: str, flaws: list[dict]) -> str:
    """Small Markdown renderer for review files. Paragraphs, list items and table rows
    that match a planted flaw get data-flaws and badges, the same units score.py scores."""
    out: list[str] = []
    lines = text.splitlines()
    i = 0

    def tagged(src: str) -> tuple[str, str]:
        return _tag(src, flaws)

    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith("```"):
            j = i + 1
            while j < len(lines) and not lines[j].startswith("```"):
                j += 1
            out.append("<pre><code>" + html.escape("\n".join(lines[i + 1:j])) + "</code></pre>")
            i = j + 1
            continue
        h = re.match(r"^(#{1,6})\s+(.*)", line)
        if h:
            lvl = min(len(h.group(1)) + 2, 6)
            out.append(f"<h{lvl}>{_inline(h.group(2))}</h{lvl}>")
            i += 1
            continue
        if re.match(r"^-{3,}\s*$", line):
            out.append("<hr>")
            i += 1
            continue
        if line.lstrip().startswith("|"):
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append(lines[i])
                i += 1
            out.append(_table(rows, tagged))
            continue
        if re.match(r"^\s{0,3}(\d+\.|[-*])\s", line):
            items: list[str] = []
            ordered = bool(re.match(r"^\s{0,3}\d+\.", line))
            start = int(re.match(r"^\s*(\d+)", line).group(1)) if ordered else 1
            while i < len(lines) and lines[i].strip() and (
                    re.match(r"^\s{0,3}(\d+\.|[-*])\s", lines[i]) or lines[i].startswith((" ", "\t"))):
                if re.match(r"^\s{0,3}(\d+\.|[-*])\s", lines[i]):
                    items.append(lines[i])
                else:
                    items[-1] += "\n" + lines[i]
                i += 1
            tag = "ol" if ordered else "ul"
            attr = f' start="{start}"' if ordered and start != 1 else ""
            lis = []
            for it in items:
                a, b = tagged(it)
                body = re.sub(r"^\s{0,3}(\d+\.|[-*])\s+", "", it)
                body = "<br>".join(_inline(x.strip()) for x in body.split("\n"))
                lis.append(f"<li{a}>{b}{body}</li>")
            out.append(f"<{tag}{attr}>" + "".join(lis) + f"</{tag}>")
            continue
        para = [line]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(
                r"^(#{1,6}\s|\s{0,3}(\d+\.|[-*])\s|\||```)", lines[i]):
            para.append(lines[i])
            i += 1
        src = "\n".join(para)
        a, b = tagged(src)
        out.append(f"<p{a}>{b}" + "<br>".join(_inline(p) for p in para) + "</p>")
    return "\n".join(out)


def _table(rows: list[str], tagged) -> str:
    def cells(r: str) -> list[str]:
        return [c.strip() for c in r.strip().strip("|").split("|")]
    body = [r for r in rows if not re.match(r"^\s*\|[\s:|-]+\|\s*$", r)]
    has_header = len(rows) > 1 and re.match(r"^\s*\|[\s:|-]+\|\s*$", rows[1])
    out = ['<div class="tablewrap"><table>']
    if has_header:
        out.append("<thead><tr>" + "".join(f"<th>{_inline(c)}</th>" for c in cells(body[0])) + "</tr></thead>")
        body = body[1:]
    out.append("<tbody>")
    for r in body:
        a, b = tagged(r)
        cs = cells(r)
        tds = "".join(f"<td>{(b if k == 0 else '')}{_inline(c)}</td>" for k, c in enumerate(cs))
        out.append(f"<tr{a}>{tds}</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


# =========================================================================== SVG (README)
SVG_FONT = 'font-family="system-ui,-apple-system,Segoe UI,sans-serif"'


def _svg(w: int, h: int, body: str, title: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'role="img" aria-label="{html.escape(title)}" {SVG_FONT}>'
            f'<title>{html.escape(title)}</title>'
            f'<rect width="{w}" height="{h}" rx="12" fill="#fcfcfb"/>{body}</svg>\n')


def svg_scorecard(rs: RunSet, flaws: list[dict]) -> str:
    cw, ch, left, top = 64, 34, 150, 104
    w = left + cw * len(flaws) + 24
    legend_lines = _wrap([f'{f["id"]} {f["title"]}' for f in flaws], 95)
    h = top + ch * len(rs.runs) + 22 + 16 * len(legend_lines)
    b = [f'<text x="24" y="34" font-size="17" font-weight="650" fill="#0b0b0b">Which reviewer caught which planted flaw</text>',
         f'<text x="24" y="54" font-size="12.5" fill="#52514e">{html.escape(rs.name)} · ✓ found · ✗ missed</text>',
         _arm_legend([a for a in ARM_ORDER if any(r.arm == a for r in rs.runs)], 24, 74)]
    for j, f in enumerate(flaws):
        b.append(f'<text x="{left + j * cw + cw / 2}" y="{top - 8}" font-size="12" font-weight="600" '
                 f'fill="#52514e" text-anchor="middle">{f["id"]}</text>')
    for i, r in enumerate(rs.runs):
        y = top + i * ch
        b.append(f'<rect x="24" y="{y + 9}" width="10" height="10" rx="2" fill="{ARM_COLOR_LIGHT.get(r.arm, "#898781")}"/>')
        b.append(f'<text x="40" y="{y + 19}" font-size="12.5" fill="#0b0b0b">{html.escape(r.name)}</text>')
        for j, f in enumerate(flaws):
            ok = r.found[f["id"]]
            fill = "#0ca30c" if ok else "#d03b3b"
            b.append(f'<rect x="{left + j * cw + 2}" y="{y + 2}" width="{cw - 4}" height="{ch - 4}" rx="4" fill="{fill}"/>')
            b.append(f'<text x="{left + j * cw + cw / 2}" y="{y + ch / 2 + 5}" font-size="14" font-weight="700" '
                     f'fill="#ffffff" text-anchor="middle">{"✓" if ok else "✗"}</text>')
    for k, line in enumerate(legend_lines):
        b.append(f'<text x="24" y="{top + ch * len(rs.runs) + 24 + 16 * k}" font-size="11.5" fill="#52514e">{html.escape(line)}</text>')
    return _svg(w, h, "".join(b), f"Planted flaws found per run, {rs.name}")


def _wrap(items: list[str], width: int) -> list[str]:
    lines, cur = [], ""
    for it in items:
        nxt = f"{cur} · {it}" if cur else it
        if len(nxt) > width and cur:
            lines.append(cur)
            cur = it
        else:
            cur = nxt
    return lines + ([cur] if cur else [])


def _arm_legend(arms: list[str], x: int, y: int) -> str:
    out, cx = [], x
    for a in arms:
        label = ARM_LABEL.get(a, a)
        out.append(f'<rect x="{cx}" y="{y - 9}" width="10" height="10" rx="2" fill="{ARM_COLOR_LIGHT.get(a, "#898781")}"/>'
                   f'<text x="{cx + 15}" y="{y}" font-size="12" fill="#52514e">{html.escape(label)}</text>')
        cx += 15 + 7 * len(label) + 22
    return "".join(out)


def svg_bars(rs: RunSet, metric: str, title: str, fmt) -> str:
    vals = [getattr(r, metric) for r in rs.runs]
    vmax = max(vals) or 1
    left, top, bh, gap, plot_w = 150, 70, 22, 8, 420
    w = left + plot_w + 90
    h = top + (bh + gap) * len(rs.runs) + 24
    b = [f'<text x="24" y="34" font-size="17" font-weight="650" fill="#0b0b0b">{html.escape(title)}</text>',
         f'<text x="24" y="52" font-size="12.5" fill="#52514e">{html.escape(rs.name)}</text>',
         _arm_legend([a for a in ARM_ORDER if any(r.arm == a for r in rs.runs)], 120, 52),
         f'<line x1="{left}" x2="{left}" y1="{top - 4}" y2="{h - 18}" stroke="#c3c2b7" stroke-width="1"/>']
    for i, r in enumerate(rs.runs):
        y = top + i * (bh + gap)
        bw = max(2, plot_w * getattr(r, metric) / vmax)
        color = ARM_COLOR_LIGHT.get(r.arm, "#898781")
        b.append(f'<text x="{left - 10}" y="{y + bh / 2 + 4.5}" font-size="12.5" fill="#0b0b0b" text-anchor="end">{html.escape(r.name)}</text>')
        b.append(f'<path d="M{left},{y} h{bw - 4} a4,4 0 0 1 4,4 v{bh - 8} a4,4 0 0 1 -4,4 h{-(bw - 4)} z" fill="{color}"/>')
        b.append(f'<text x="{left + bw + 8}" y="{y + bh / 2 + 4.5}" font-size="12.5" fill="#52514e">{fmt(getattr(r, metric))}</text>')
    return _svg(w, h, "".join(b), f"{title}, {rs.name}")


def write_svgs(rs: RunSet, flaws: list[dict]) -> list[Path]:
    out = rs.path / "visuals"
    out.mkdir(exist_ok=True)
    files = {
        "scorecard.svg": svg_scorecard(rs, flaws),
        "cost.svg": svg_bars(rs, "cost_usd", "Cost per run (CLI-reported, API rates)", lambda v: f"${v:.2f}"),
        "time.svg": svg_bars(rs, "duration_s", "Wall-clock time per run", lambda v: f"{v:.0f} s"),
        "findings.svg": svg_bars(rs, "findings", "Findings reported per run", lambda v: f"{v:.0f}"),
    }
    paths = []
    for name, svg in files.items():
        p = out / name
        p.write_text(svg, encoding="utf-8")
        paths.append(p)
    return paths


# =========================================================================== HTML report
def runset_payload(rs: RunSet, flaws: list[dict]) -> dict:
    return {
        "name": rs.name,
        "claude_version": rs.manifest.get("claude_version"),
        "egm_ref": rs.manifest.get("egm_ref"),
        "runs": [{
            "name": r.name, "arm": r.arm, "found": r.found, "foundCount": sum(r.found.values()),
            "findings": r.findings, "severity": r.severity, "duration": round(r.duration_s, 1),
            "turns": r.turns, "cost": round(r.cost_usd, 4), "models": r.models,
            "html": render_markdown(r.review, flaws),
            "stages": [{"name": k, "html": render_markdown(v, flaws)} for k, v in r.stage_reports.items()],
        } for r in rs.runs],
    }


def build_html(runsets: list[RunSet], flaws: list[dict]) -> str:
    data = {
        "flaws": [{"id": f["id"], "title": f["title"], "category": f["category"],
                   "description": f["description"]} for f in flaws],
        "arms": {a: {"label": ARM_LABEL.get(a, a), "light": ARM_COLOR_LIGHT.get(a), "dark": ARM_COLOR_DARK.get(a)}
                 for a in ARM_ORDER},
        "runsets": [runset_payload(rs, flaws) for rs in runsets],
    }
    blob = json.dumps(data).replace("</", "<\\/")
    return TEMPLATE.replace("/*__DATA__*/null", blob)


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EGM review experiment</title>
<style>
:root{color-scheme:light;
  --page:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--grid:#e1e0d9;--axis:#c3c2b7;
  --ring:rgba(11,11,11,.10);--good:#0ca30c;--bad:#d03b3b;--hl:#fff4cc;--hl-ring:#eda100;
  --egm:#2a78d6;--fresh:#eb6834;--ctx:#1baf7a;--sev-blocker:#1c5cab;--sev-major:#5598e7;--sev-nit:#86b6ef;
  --code:#f0efec}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])){color-scheme:dark;
  --page:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--muted:#898781;--grid:#2c2c2a;--axis:#383835;
  --ring:rgba(255,255,255,.10);--hl:#3a3110;--hl-ring:#c98500;
  --egm:#3987e5;--fresh:#d95926;--ctx:#199e70;--sev-blocker:#6da7ec;--sev-major:#256abf;--sev-nit:#184f95;--code:#262624}}
:root[data-theme="dark"]{color-scheme:dark;
  --page:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--muted:#898781;--grid:#2c2c2a;--axis:#383835;
  --ring:rgba(255,255,255,.10);--hl:#3a3110;--hl-ring:#c98500;
  --egm:#3987e5;--fresh:#d95926;--ctx:#199e70;--sev-blocker:#6da7ec;--sev-major:#256abf;--sev-nit:#184f95;--code:#262624}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1120px;margin:0 auto;padding:28px 16px 64px}
h1{font-size:28px;line-height:1.2;margin:0 0 6px;letter-spacing:-.01em}
h2{font-size:19px;margin:0 0 4px}
.sub{color:var(--ink2);margin:0 0 4px}
.muted{color:var(--muted);font-size:13px}
a{color:var(--egm)}
.card{background:var(--surface);border:1px solid var(--ring);border-radius:14px;padding:20px;margin-top:18px}
.row{display:flex;gap:12px;flex-wrap:wrap;align-items:center}
.seg{display:inline-flex;border:1px solid var(--ring);border-radius:10px;overflow:hidden}
.seg button{background:transparent;border:0;padding:7px 12px;color:var(--ink2);font:inherit;font-size:13.5px;cursor:pointer}
.seg button[aria-pressed="true"]{background:var(--ink);color:var(--surface)}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-top:16px}
.tile{background:var(--surface);border:1px solid var(--ring);border-radius:14px;padding:16px}
.tile .v{font-size:30px;font-weight:650;line-height:1.1;margin-top:4px}
.tile .l{color:var(--ink2);font-size:13px}
.tile .d{color:var(--muted);font-size:12.5px;margin-top:4px}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:18px}
.legend{display:flex;gap:14px;flex-wrap:wrap;font-size:13px;color:var(--ink2);margin:8px 0 2px}
.sw{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px;vertical-align:-1px}
/* scorecard */
.score{width:100%;border-collapse:separate;border-spacing:3px;font-size:13px}
.score th{color:var(--ink2);font-weight:600;padding:2px 4px;text-align:center}
.score th.rn{text-align:left;white-space:nowrap}
.score td.c{height:34px;border-radius:5px;text-align:center;color:#fff;font-weight:700;cursor:pointer;min-width:38px}
.score td.c.y{background:var(--good)}.score td.c.n{background:var(--bad)}
.score td.c:hover,.score td.c:focus-visible{outline:2px solid var(--ink);outline-offset:1px}
.score td.tot{color:var(--ink2);text-align:right;padding-left:8px;font-variant-numeric:tabular-nums;white-space:nowrap}
/* bars */
.bars{width:100%}
.bars .lab{fill:var(--ink);font-size:12.5px}.bars .val{fill:var(--ink2);font-size:12.5px;font-variant-numeric:tabular-nums}
.bars .base{stroke:var(--axis)}.bars .gl{stroke:var(--grid)}
.bars .hit{fill:transparent;cursor:default}
.tip{position:fixed;pointer-events:none;background:var(--ink);color:var(--surface);font-size:12.5px;padding:7px 9px;border-radius:8px;
  opacity:0;transition:opacity .08s;z-index:10;max-width:280px;line-height:1.4}
/* flaws */
.flaws{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px;margin-top:12px}
.flaw{border:1px solid var(--ring);border-radius:10px;padding:10px 12px;cursor:pointer;background:transparent;color:inherit;text-align:left;font:inherit}
.flaw[aria-pressed="true"]{border-color:var(--hl-ring);box-shadow:0 0 0 1px var(--hl-ring);background:var(--hl)}
.flaw b{font-size:13px}.flaw .t{font-size:13.5px;font-weight:600}.flaw .x{font-size:12.5px;color:var(--ink2)}
/* explorer */
.tabs{display:flex;gap:6px;flex-wrap:wrap;margin:12px 0}
.tab{border:1px solid var(--ring);background:transparent;color:var(--ink2);border-radius:999px;padding:5px 12px;font:inherit;font-size:13px;cursor:pointer}
.tab[aria-selected="true"]{color:var(--ink);border-color:var(--ink);font-weight:600}
.tab .k{font-variant-numeric:tabular-nums;color:var(--muted);margin-left:4px}
.doc{border-top:1px solid var(--grid);padding-top:8px;max-height:720px;overflow:auto}
.doc h3,.doc h4,.doc h5,.doc h6{margin:18px 0 6px;font-size:15.5px}
.doc table{border-collapse:collapse;font-size:13.5px;width:100%}
.doc th,.doc td{border-bottom:1px solid var(--grid);padding:6px 8px;text-align:left;vertical-align:top}
.doc .tablewrap{overflow-x:auto}
.doc code{background:var(--code);padding:1px 4px;border-radius:4px;font-size:.92em}
.doc pre{background:var(--code);padding:10px;border-radius:8px;overflow:auto}
.doc li,.doc p,.doc tr{border-radius:6px;transition:background .1s}
.doc [data-flaws].on{background:var(--hl);box-shadow:inset 3px 0 0 var(--hl-ring)}
.doc li.on,.doc p.on{padding:2px 6px;margin-left:-6px}
.badge{display:inline-block;font-size:11px;font-weight:700;border:1px solid var(--ring);color:var(--ink2);border-radius:5px;padding:0 5px;margin-right:4px;vertical-align:1px}
.badge.hit{background:var(--hl-ring);border-color:var(--hl-ring);color:#0b0b0b}
.note{font-size:13px;color:var(--ink2);margin-top:8px}
.tablebtn{font:inherit;font-size:12.5px;background:transparent;border:1px solid var(--ring);border-radius:8px;color:var(--ink2);padding:4px 9px;cursor:pointer}
.datatable{width:100%;border-collapse:collapse;font-size:13px;margin-top:10px;font-variant-numeric:tabular-nums}
.datatable th,.datatable td{border-bottom:1px solid var(--grid);padding:5px 8px;text-align:right}
.datatable th:first-child,.datatable td:first-child{text-align:left}
footer{margin-top:28px;color:var(--muted);font-size:12.5px}
@media (max-width:600px){h1{font-size:23px}.score{font-size:12px}.score td.c{min-width:28px}}
</style>
</head>
<body>
<main>
  <h1>Who caught the planted flaws?</h1>
  <p class="sub">Seven flaws were planted in a design doc. Three kinds of reviewer looked for them: Google's Elephant-Goldfish Model (EGM), a plain fresh-session review, and a same-session ("in-context") review.</p>
  <div class="row" style="margin-top:12px">
    <span class="muted">Run set</span><div class="seg" id="rsSeg"></div>
    <span class="muted" id="rsMeta"></span>
    <span style="flex:1"></span>
    <div class="seg" id="themeSeg"><button data-t="auto">Auto</button><button data-t="light">Light</button><button data-t="dark">Dark</button></div>
  </div>

  <div class="tiles" id="tiles"></div>

  <section class="card">
    <h2>Scorecard</h2>
    <p class="muted">Click a cell to open that review with the matching finding highlighted.</p>
    <div class="legend" id="armLegend"></div>
    <div style="overflow-x:auto"><table class="score" id="score"></table></div>
  </section>

  <div class="grid2">
    <section class="card"><h2>Cost per run</h2><p class="muted">As reported by the CLI at API rates.</p><div id="cCost"></div></section>
    <section class="card"><h2>Time per run</h2><p class="muted">Wall clock. In-context runs include both turns.</p><div id="cTime"></div></section>
  </div>
  <section class="card">
    <h2>Findings per run, by severity</h2>
    <p class="muted">Counted from each review's Blocker / Major / Nit sections.</p>
    <div class="legend"><span><i class="sw" style="background:var(--sev-blocker)"></i>Blocker</span><span><i class="sw" style="background:var(--sev-major)"></i>Major</span><span><i class="sw" style="background:var(--sev-nit)"></i>Nit</span></div>
    <div id="cSev"></div>
    <button class="tablebtn" id="tblBtn" aria-expanded="false">Show as table</button>
    <div id="tbl" hidden></div>
  </section>

  <section class="card">
    <h2>Review explorer</h2>
    <p class="muted">Pick a flaw to highlight where each reviewer caught it. Badges mark every finding that matches a planted flaw.</p>
    <div class="flaws" id="flaws"></div>
    <div class="tabs" id="tabs" role="tablist"></div>
    <div class="tabs" id="stageTabs" role="tablist"></div>
    <div class="doc" id="doc" role="tabpanel"></div>
    <p class="note">Matching uses the same patterns as <code>scripts/score.py</code> (<code>experiment/planted_flaws.json</code>). It's a first pass: read the text.</p>
  </section>

  <footer>Generated by <code>scripts/build_report.py</code> from the files in <code>results/</code>. Single file, no network requests.</footer>
</main>
<div class="tip" id="tip" role="status"></div>
<script>
const DATA = /*__DATA__*/null;
const $ = s => document.querySelector(s);
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const armVar = a => ({egm:"var(--egm)",fresh:"var(--fresh)","in-context":"var(--ctx)"}[a] || "var(--muted)");
let rsIdx = 0, runIdx = 0, stageIdx = -1, flaw = null;
const tip = $("#tip");
function showTip(e, html){tip.innerHTML = html; tip.style.opacity = 1;
  const x = Math.min(e.clientX + 14, innerWidth - tip.offsetWidth - 8), y = Math.min(e.clientY + 14, innerHeight - tip.offsetHeight - 8);
  tip.style.left = x + "px"; tip.style.top = y + "px";}
function hideTip(){tip.style.opacity = 0}

// theme
function setTheme(t){ if(t==="auto") document.documentElement.removeAttribute("data-theme"); else document.documentElement.dataset.theme=t;
  document.querySelectorAll("#themeSeg button").forEach(b=>b.setAttribute("aria-pressed", b.dataset.t===t));
  try{localStorage.setItem("egm-theme",t)}catch(e){} }
document.querySelectorAll("#themeSeg button").forEach(b=>b.onclick=()=>setTheme(b.dataset.t));
let saved="auto"; try{saved=localStorage.getItem("egm-theme")||"auto"}catch(e){} setTheme(saved);

function rs(){return DATA.runsets[rsIdx]}
function fmtCost(v){return "$"+v.toFixed(2)}
function fmtTime(v){return v>=90? (v/60).toFixed(1)+" min" : Math.round(v)+" s"}
function median(a){const s=[...a].sort((x,y)=>x-y), m=s.length>>1; return s.length%2? s[m] : (s[m-1]+s[m])/2}

function renderRsSeg(){
  $("#rsSeg").innerHTML = DATA.runsets.map((r,i)=>`<button data-i="${i}" aria-pressed="${i===rsIdx}">${esc(r.name)}</button>`).join("");
  document.querySelectorAll("#rsSeg button").forEach(b=>b.onclick=()=>{rsIdx=+b.dataset.i; runIdx=0; stageIdx=-1; renderAll()});
  const r = rs(); $("#rsMeta").textContent = [r.claude_version && "Claude Code "+r.claude_version.replace(/ \(.*\)/,""), r.egm_ref && "EGM @ "+r.egm_ref].filter(Boolean).join(" · ");
}

function renderTiles(){
  const runs = rs().runs, n = DATA.flaws.length, by = a => runs.filter(r=>r.arm===a);
  const all = runs.every(r=>r.foundCount===n);
  const egm = by("egm"), fresh = by("fresh"), ctx = by("in-context");
  const tiles = [
    {l:"Planted flaws found", v: all? `${n}/${n} in every run` : `${runs.filter(r=>r.foundCount===n).length} of ${runs.length} runs found all ${n}`, d:`${runs.length} runs across ${new Set(runs.map(r=>r.arm)).size} reviewer types`},
  ];
  if(egm.length && fresh.length){
    tiles.push({l:"Cost per run, median", v:`${fmtCost(median(egm.map(r=>r.cost)))} vs ${fmtCost(median(fresh.map(r=>r.cost)))}`, d:"EGM vs fresh session"});
    tiles.push({l:"Time per run, median", v:`${fmtTime(median(egm.map(r=>r.duration)))} vs ${fmtTime(median(fresh.map(r=>r.duration)))}`, d:"EGM vs fresh session"});
    tiles.push({l:"Findings per run, median", v:`${median(egm.map(r=>r.findings))} vs ${median(fresh.map(r=>r.findings))}`, d:"EGM vs fresh session"});
  }
  $("#tiles").innerHTML = tiles.map(t=>`<div class="tile"><div class="l">${esc(t.l)}</div><div class="v">${esc(t.v)}</div><div class="d">${esc(t.d)}</div></div>`).join("");
}

function renderLegend(){
  const arms = [...new Set(rs().runs.map(r=>r.arm))];
  $("#armLegend").innerHTML = arms.map(a=>`<span><i class="sw" style="background:${armVar(a)}"></i>${esc(DATA.arms[a]?.label||a)}</span>`).join("")
    + `<span><i class="sw" style="background:var(--good)"></i>✓ found</span><span><i class="sw" style="background:var(--bad)"></i>✗ missed</span>`;
}

function renderScore(){
  const f = DATA.flaws, runs = rs().runs;
  let h = `<thead><tr><th class="rn">Run</th>${f.map(x=>`<th title="${esc(x.title)}">${x.id}</th>`).join("")}<th></th></tr></thead><tbody>`;
  runs.forEach((r,i)=>{
    h += `<tr><th class="rn"><i class="sw" style="background:${armVar(r.arm)}"></i>${esc(r.name)}</th>`;
    f.forEach(x=>{const ok=r.found[x.id];
      h += `<td class="c ${ok?"y":"n"}" tabindex="0" data-run="${i}" data-flaw="${x.id}" aria-label="${esc(r.name)} ${x.id} ${ok?"found":"missed"}">${ok?"✓":"✗"}</td>`;});
    h += `<td class="tot">${r.foundCount}/${f.length}</td></tr>`;
  });
  $("#score").innerHTML = h + "</tbody>";
  document.querySelectorAll("#score td.c").forEach(td=>{
    const go=()=>{runIdx=+td.dataset.run; stageIdx=-1; flaw=td.dataset.flaw; renderExplorer(); $("#doc").scrollIntoView({behavior:"smooth",block:"start"})};
    td.onclick=go; td.onkeydown=e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();go()}};
    td.onmousemove=e=>{const r=rs().runs[+td.dataset.run], x=DATA.flaws.find(q=>q.id===td.dataset.flaw);
      showTip(e, `<b>${esc(r.name)} · ${x.id}</b><br>${esc(x.title)}<br>${r.found[x.id]?"✓ found":"✗ missed"} · click to open`)};
    td.onmouseleave=hideTip;
  });
}

function hbars(el, runs, key, fmt){
  const W = Math.max(320, el.clientWidth||520), left = 118, right = 64, bh = 22, gap = 9, top = 6;
  const max = Math.max(...runs.map(r=>r[key])) || 1, pw = W-left-right, H = top + runs.length*(bh+gap) + 4;
  let s = `<svg class="bars" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(key)} per run">`;
  for(let t=0;t<=4;t++){const x=left+pw*t/4; s+=`<line class="gl" x1="${x}" x2="${x}" y1="${top}" y2="${H-4}" stroke-width="1"/>`}
  runs.forEach((r,i)=>{const y=top+i*(bh+gap), w=Math.max(4,pw*r[key]/max);
    s += `<text class="lab" x="${left-10}" y="${y+bh/2+4.5}" text-anchor="end">${esc(r.name)}</text>`;
    s += `<path d="M${left},${y} h${w-4} a4,4 0 0 1 4,4 v${bh-8} a4,4 0 0 1 -4,4 h${-(w-4)} z" fill="${armVar(r.arm)}"/>`;
    s += `<text class="val" x="${left+w+7}" y="${y+bh/2+4.5}">${fmt(r[key])}</text>`;
    s += `<rect class="hit" x="0" y="${y-gap/2}" width="${W}" height="${bh+gap}" data-i="${i}"/>`;});
  s += `<line class="base" x1="${left}" x2="${left}" y1="${top-2}" y2="${H-4}" stroke-width="1"/></svg>`;
  el.innerHTML = s;
  el.querySelectorAll(".hit").forEach(h=>{h.onmousemove=e=>{const r=runs[+h.dataset.i];
    showTip(e,`<b>${esc(r.name)}</b> · ${esc(DATA.arms[r.arm]?.label||r.arm)}<br>Cost ${fmtCost(r.cost)} · ${fmtTime(r.duration)} · ${r.turns} turns<br>${r.findings} findings · ${r.foundCount}/${DATA.flaws.length} flaws`)}; h.onmouseleave=hideTip});
}

function sevbars(el, runs){
  const W = Math.max(320, el.clientWidth||900), left=118, right=40, bh=22, gap=9, top=6;
  const tot = r => r.severity.Blocker + r.severity.Major + r.severity.Nit;
  const max = Math.max(...runs.map(tot)) || 1, pw = W-left-right, H = top + runs.length*(bh+gap)+4;
  const cols = {Blocker:"var(--sev-blocker)",Major:"var(--sev-major)",Nit:"var(--sev-nit)"};
  let s = `<svg class="bars" viewBox="0 0 ${W} ${H}" role="img" aria-label="Findings by severity per run">`;
  runs.forEach((r,i)=>{const y=top+i*(bh+gap); let x=left;
    s += `<text class="lab" x="${left-10}" y="${y+bh/2+4.5}" text-anchor="end">${esc(r.name)}</text>`;
    const segs = ["Blocker","Major","Nit"].filter(k=>r.severity[k]>0);
    segs.forEach((k,j)=>{const w=pw*r.severity[k]/max, last=j===segs.length-1, gapw = last?0:2;
      if(last) s += `<path d="M${x},${y} h${Math.max(0,w-4)} a4,4 0 0 1 4,4 v${bh-8} a4,4 0 0 1 -4,4 h${-Math.max(0,w-4)} z" fill="${cols[k]}"/>`;
      else s += `<rect x="${x}" y="${y}" width="${Math.max(1,w-gapw)}" height="${bh}" fill="${cols[k]}"/>`;
      x += w;});
    s += `<text class="val" x="${x+7}" y="${y+bh/2+4.5}">${tot(r)}</text>`;
    s += `<rect class="hit" x="0" y="${y-gap/2}" width="${W}" height="${bh+gap}" data-i="${i}"/>`;});
  s += `<line class="base" x1="${left}" x2="${left}" y1="${top-2}" y2="${H-4}" stroke-width="1"/></svg>`;
  el.innerHTML = s;
  el.querySelectorAll(".hit").forEach(h=>{h.onmousemove=e=>{const r=runs[+h.dataset.i];
    showTip(e,`<b>${esc(r.name)}</b><br>Blocker ${r.severity.Blocker} · Major ${r.severity.Major} · Nit ${r.severity.Nit}`)}; h.onmouseleave=hideTip});
}

function renderTable(){
  const runs = rs().runs;
  $("#tbl").innerHTML = `<table class="datatable"><thead><tr><th>Run</th><th>Flaws found</th><th>Findings</th><th>Blocker</th><th>Major</th><th>Nit</th><th>Time</th><th>Turns</th><th>Cost</th></tr></thead><tbody>`
    + runs.map(r=>`<tr><td>${esc(r.name)}</td><td>${r.foundCount}/${DATA.flaws.length}</td><td>${r.findings}</td><td>${r.severity.Blocker}</td><td>${r.severity.Major}</td><td>${r.severity.Nit}</td><td>${fmtTime(r.duration)}</td><td>${r.turns}</td><td>${fmtCost(r.cost)}</td></tr>`).join("")
    + "</tbody></table>";
}
$("#tblBtn").onclick=()=>{const t=$("#tbl"), open=t.hidden; t.hidden=!open; $("#tblBtn").setAttribute("aria-expanded",open); $("#tblBtn").textContent=open?"Hide table":"Show as table"};

function renderCharts(){
  const runs = rs().runs;
  hbars($("#cCost"), runs, "cost", fmtCost);
  hbars($("#cTime"), runs, "duration", fmtTime);
  sevbars($("#cSev"), runs);
  renderTable();
}

function renderFlaws(){
  $("#flaws").innerHTML = DATA.flaws.map(f=>`<button class="flaw" data-f="${f.id}" aria-pressed="${flaw===f.id}"><b>${f.id}</b> · <span class="x">${esc(f.category)}</span><div class="t">${esc(f.title)}</div><div class="x">${esc(f.description)}</div></button>`).join("");
  document.querySelectorAll("#flaws .flaw").forEach(b=>b.onclick=()=>{flaw = flaw===b.dataset.f? null : b.dataset.f; renderExplorer()});
}

function renderExplorer(){
  renderFlaws();
  const runs = rs().runs, r = runs[runIdx];
  $("#tabs").innerHTML = runs.map((x,i)=>{const k = flaw? (x.found[flaw]?" ✓":" ✗") : "";
    return `<button class="tab" role="tab" aria-selected="${i===runIdx}" data-i="${i}"><i class="sw" style="background:${armVar(x.arm)}"></i>${esc(x.name)}<span class="k">${k}</span></button>`}).join("");
  document.querySelectorAll("#tabs .tab").forEach(b=>b.onclick=()=>{runIdx=+b.dataset.i; stageIdx=-1; renderExplorer()});
  const st = r.stages || [];
  $("#stageTabs").innerHTML = st.length? `<button class="tab" role="tab" aria-selected="${stageIdx<0}" data-i="-1">Consolidated report</button>` + st.map((s,i)=>`<button class="tab" role="tab" aria-selected="${i===stageIdx}" data-i="${i}">Stage: ${esc(s.name)}</button>`).join("") : "";
  $("#stageTabs").hidden = !st.length;
  document.querySelectorAll("#stageTabs .tab").forEach(b=>b.onclick=()=>{stageIdx=+b.dataset.i; renderExplorer()});
  const doc = $("#doc");
  doc.innerHTML = stageIdx>=0? st[stageIdx].html : r.html;
  let first = null;
  doc.querySelectorAll("[data-flaws]").forEach(el=>{
    const on = flaw && el.dataset.flaws.split(" ").includes(flaw);
    el.classList.toggle("on", !!on); if(on && !first) first = el;
  });
  doc.querySelectorAll(".badge").forEach(b=>b.classList.toggle("hit", b.dataset.f===flaw));
  if(first){ doc.scrollTop = first.offsetTop - doc.offsetTop - 12 } else doc.scrollTop = 0;
}

function renderAll(){renderRsSeg(); renderTiles(); renderLegend(); renderScore(); renderCharts(); renderExplorer()}
renderAll();
let rt; addEventListener("resize",()=>{clearTimeout(rt); rt=setTimeout(renderCharts,120)});
</script>
</body>
</html>
"""


# =========================================================================== main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dirs", nargs="*", type=Path, help="result folders (default: every folder in results/)")
    ap.add_argument("--flaws", type=Path, default=FLAWS_PATH)
    ap.add_argument("--out", type=Path, default=ROOT / "report" / "index.html")
    ap.add_argument("--no-svg", action="store_true", help="skip the README SVGs")
    args = ap.parse_args(argv)
    flaws = json.loads(args.flaws.read_text(encoding="utf-8"))["flaws"]
    dirs = args.run_dirs or sorted((p for p in (ROOT / "results").iterdir() if p.is_dir()), reverse=False)
    runsets = [load_runset(d, flaws) for d in dirs]
    runsets = [r for r in runsets if r.runs]
    if not runsets:
        print("no scored runs found", file=sys.stderr)
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(build_html(runsets, flaws), encoding="utf-8")
    print(f"wrote {args.out}")
    if not args.no_svg:
        for rs in runsets:
            for p in write_svgs(rs, flaws):
                print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
