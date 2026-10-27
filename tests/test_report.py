import json
import re
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_report as br  # noqa: E402
import score  # noqa: E402

FLAWS = json.loads((ROOT / "experiment" / "planted_flaws.json").read_text())["flaws"]
REFERENCE = ROOT / "results" / "2026-10-27"


class Markdown(unittest.TestCase):
    def test_escapes_html(self):
        out = br.render_markdown("1. <script>alert(1)</script> is **bold**", FLAWS)
        self.assertNotIn("<script>", out)
        self.assertIn("<strong>bold</strong>", out)

    def test_table_and_list(self):
        out = br.render_markdown("| A | B |\n|---|---|\n| 1 | `x` |\n\n- one\n- two", FLAWS)
        self.assertIn("<th>A</th>", out)
        self.assertIn("<code>x</code>", out)
        self.assertEqual(out.count("<li"), 2)

    def test_matching_finding_is_tagged(self):
        out = br.render_markdown("1. The method `get_url` does not exist.\n2. Typo.", FLAWS)
        self.assertIn('data-flaws="F1"', out)
        self.assertEqual(out.count("data-flaws"), 1)


class Severity(unittest.TestCase):
    def test_counts_by_heading(self):
        text = "## Blocker\n\n1. a\n2. b\n\n## Major\n\n1. c\n\n## Nit\n\n1. d\n2. e\n3. f"
        self.assertEqual(br.severity_counts(text), {"Blocker": 2, "Major": 1, "Nit": 3})

    def test_table_ids_counted_once(self):
        text = "## 🔴 Blockers\n| B1 | x |\n| B2 | y |\n## Traceability\n| B1 | 2 |"
        self.assertEqual(br.severity_counts(text)["Blocker"], 2)


@unittest.skipUnless(REFERENCE.exists(), "reference results not present")
class ReferenceReport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rs = br.load_runset(REFERENCE, FLAWS)

    def test_highlights_agree_with_scorer(self):
        """Every flaw the scorer counts as found is highlighted somewhere in that review."""
        for r in self.rs.runs:
            tagged = set(re.findall(r'data-flaws="([^"]+)"', br.render_markdown(r.review, FLAWS)))
            ids = {i for group in tagged for i in group.split()}
            self.assertEqual(ids, {k for k, v in r.found.items() if v}, r.name)

    def test_severity_totals_match_findings(self):
        for r in self.rs.runs:
            self.assertEqual(sum(r.severity.values()), r.findings, r.name)

    def test_html_is_self_contained(self):
        page = br.build_html([self.rs], FLAWS)
        self.assertNotRegex(page, r'<(script|link|img)[^>]+(src|href)="https?://')
        self.assertIn("egm-1", page)
        data = json.loads(re.search(r"const DATA = (\{.*?\});\n", page, re.S).group(1).replace("<\\/", "</"))
        self.assertEqual(len(data["runsets"][0]["runs"]), 7)

    def test_svgs_are_valid_xml(self):
        with tempfile.TemporaryDirectory() as tmp:
            rs = br.RunSet(self.rs.name, Path(tmp), self.rs.runs, {})
            for p in br.write_svgs(rs, FLAWS):
                ET.parse(p)

    def test_main_writes_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "r.html"
            self.assertEqual(br.main([str(REFERENCE), "--out", str(out), "--no-svg"]), 0)
            self.assertTrue(out.stat().st_size > 10_000)


if __name__ == "__main__":
    unittest.main()
