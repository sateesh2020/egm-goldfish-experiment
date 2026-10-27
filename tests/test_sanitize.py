import io
import json
import sys
import tarfile
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import sanitize_results as sr  # noqa: E402


class Sanitize(unittest.TestCase):
    def test_redact_email_and_paths(self):
        text, n = sr.redact("mail jane.doe@corp.example at /Users/jane/work/x/workspace/review.md and /tmp/a/b.txt")
        self.assertNotIn("jane", text)
        self.assertIn("<workspace>/review.md", text)
        self.assertIn("<local-path>/b.txt", text)
        self.assertEqual(n, 3)

    def test_allowed_email_kept(self):
        self.assertEqual(sr.redact("noreply@anthropic.com")[1], 0)

    def test_folder_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "fresh-1"
            (run / "workspace").mkdir(parents=True)
            (run / "result.json").write_text(json.dumps({
                "total_cost_usd": 0.1, "num_turns": 3, "duration_ms": 10, "process_peak_rss_mib": 9,
                "result": "wrote /home/me/x/workspace/review.md"}))
            (run / "review.md").write_text("1. get_url is wrong")
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode="w:gz") as t:
                data = b'{"userEmail": "me@corp.example"}\n'
                info = tarfile.TarInfo("s/x.jsonl"); info.size = len(data)
                t.addfile(info, io.BytesIO(data))
            (run / "transcripts.tgz").write_bytes(buf.getvalue())
            with redirect_stdout(io.StringIO()):
                self.assertEqual(sr.main([tmp, "--check"]), 1)
                self.assertEqual(sr.main([tmp]), 0)
                self.assertEqual(sr.main([tmp, "--check"]), 0)
            d = json.loads((run / "result.json").read_text())
            self.assertEqual(set(d), {"total_cost_usd", "num_turns", "duration_ms", "result"})
            self.assertEqual(d["result"], "wrote <workspace>/review.md")
            self.assertFalse((run / "workspace").exists())
            with tarfile.open(run / "transcripts.tgz") as t:
                self.assertNotIn(b"me@corp", t.extractfile("s/x.jsonl").read())

    def test_committed_results_are_clean(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(sr.main([str(ROOT / "results"), "--check"]), 0)


if __name__ == "__main__":
    unittest.main()
