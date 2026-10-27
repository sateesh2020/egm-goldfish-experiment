import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import score  # noqa: E402

FLAWS = json.loads((ROOT / "experiment" / "planted_flaws.json").read_text())["flaws"]
REFERENCE = ROOT / "results" / "2026-10-27"


class SplitFindings(unittest.TestCase):
    def test_numbered_items_without_blank_lines_are_separate(self):
        text = "1. first thing\n2. second thing\n   wrapped line\n3. third"
        self.assertEqual(len(score.split_findings(text)), 3)

    def test_table_rows_are_separate_and_separator_dropped(self):
        text = "| ID | Item |\n|----|------|\n| B1 | atomic |\n| B2 | other |"
        chunks = score.split_findings(text)
        self.assertEqual(len(chunks), 3)
        self.assertTrue(all("---" not in c for c in chunks))

    def test_groups_must_match_in_the_same_finding(self):
        # "CEP" and "undefined" are in different findings, so F3 must not count
        text = "1. The CEP forwarding has no schema.\n\n2. The term QRS is undefined."
        found = score.score_review(text, FLAWS)
        self.assertFalse(found["F3"])


class ScoreReviews(unittest.TestCase):
    def test_synthetic_review_scores_only_what_it_mentions(self):
        text = (
            "## Blocker\n\n"
            "1. The method `get_url` does not exist; it is `get`.\n\n"
            "2. The read-then-write increment loses clicks under 4 workers; use an atomic update.\n\n"
            "## Nit\n\n"
            "3. Typo in the title."
        )
        found = score.score_review(text, FLAWS)
        self.assertEqual({k for k, v in found.items() if v}, {"F1", "F6"})

    def test_scope_removal_wording_counts_for_f4(self):
        # wording from a real EGM run (2026-10-27 rerun, action A3)
        text = ("**A3. Remove CEP forwarding and ML bot detection from scope; add Goals & Non-Goals.** "
                "Neither serves the stated objective.")
        self.assertTrue(score.score_review(text, FLAWS)["F4"])

    def test_bot_mentioned_without_criticism_does_not_count(self):
        self.assertFalse(score.score_review("1. The bot-detection interface is well specified.", FLAWS)["F4"])

    def test_count_findings_bold_ids(self):
        self.assertEqual(score.count_findings("**A1. Do x.** y\n\n**A2. Do z.** w\n"), 2)

    def test_empty_review_finds_nothing(self):
        self.assertEqual(sum(score.score_review("", FLAWS).values()), 0)

    def test_count_findings_dedupes_table_ids(self):
        text = "| B1 | x |\n| B2 | y |\n\n| Action | S5 |\n|---|---|\n| B1 | 2 |"
        self.assertEqual(score.count_findings(text), 2)


@unittest.skipUnless(REFERENCE.exists(), "reference results not present")
class ReferenceRun(unittest.TestCase):
    """The committed 2026-10-27 run must keep scoring the way the article reports."""

    @classmethod
    def setUpClass(cls):
        cls.rows = {r["run"]: r for r in score.score_runs(REFERENCE, FLAWS)}

    def test_all_seven_runs_present(self):
        self.assertEqual(sorted(self.rows), sorted(
            ["egm-1", "fresh-1", "fresh-2", "fresh-3", "in-context-1", "in-context-2", "in-context-3"]))

    def test_every_run_found_all_seven(self):
        for name, row in self.rows.items():
            self.assertEqual(row["found_count"], 7, name)

    def test_egm_finding_count_and_cost(self):
        egm = self.rows["egm-1"]
        self.assertEqual(egm["findings"], 26)
        self.assertAlmostEqual(egm["cost_usd"], 0.88, places=2)
        self.assertEqual(egm["turns"], 21)

    def test_in_context_sums_both_turns(self):
        r = self.rows["in-context-1"]
        self.assertEqual(r["result_files"], 2)
        self.assertGreater(r["cost_usd"], 0.18)

    def test_markdown_report(self):
        md = score.render_markdown(list(self.rows.values()), FLAWS)
        self.assertIn("| EGM `/egm-review` | 1 | 7/7 |", md)
        self.assertIn("Per flaw", md)

    def test_main_writes_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(score.main([str(REFERENCE), "--out", tmp]), 0)
            self.assertTrue((Path(tmp) / "results.md").exists())
            rows = json.loads((Path(tmp) / "scores.json").read_text())
            self.assertEqual(len(rows), 7)


if __name__ == "__main__":
    unittest.main()
