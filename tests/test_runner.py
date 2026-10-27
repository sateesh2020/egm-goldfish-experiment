"""Runner tests. A fake `claude` executable stands in for the CLI, so no API calls are made."""
import io
import json
import os
import stat
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import run_experiment as rx  # noqa: E402

FAKE_CLAUDE = textwrap.dedent("""\
    #!/usr/bin/env python3
    # Fake claude CLI: logs its argv, writes a review file like the real arms do, prints result JSON.
    import json, os, sys
    from pathlib import Path
    args = sys.argv[1:]
    if args == ["--version"]:
        print("9.9.9 (Fake Claude)"); sys.exit(0)
    log = Path(os.environ["FAKE_CLAUDE_LOG"])
    with log.open("a") as f:
        f.write(json.dumps({"cwd": os.getcwd(), "args": args}) + "\\n")
    prompt = args[args.index("-p") + 1]
    if prompt.startswith("/egm:egm-review"):
        Path("zoom_out_report.md").write_text("1. The bot framework is speculative.\\n")
        Path("consolidated_review_report.md").write_text("| B1 | The method get_url does not exist |\\n")
    elif prompt.startswith("Review the design document"):
        Path("review.md").write_text("1. `get_url` is wrong; the method is `get`.\\n")
    else:  # in-context setup turn: save the doc
        Path("docs/designs").mkdir(parents=True, exist_ok=True)
        Path("docs/designs/click_analytics.md").write_text("doc")
    print(json.dumps({"session_id": "sess-123", "duration_ms": 1000, "num_turns": 2,
                      "total_cost_usd": 0.01, "modelUsage": {"fake-model": {}}, "is_error": False}))
""")


class Commands(unittest.TestCase):
    def test_base_command_isolates_settings_and_mcp(self):
        s = rx.Settings(out=Path("/tmp/x"), model="some-model")
        cmd = rx.base_command(s, "hi", "Read Grep")
        for flag in ["-p", "--output-format", "--strict-mcp-config", "--setting-sources", "--allowedTools", "--model"]:
            self.assertIn(flag, cmd)
        self.assertEqual(cmd[cmd.index("--setting-sources") + 1], "project")
        self.assertEqual(cmd[cmd.index("--mcp-config") + 1], '{"mcpServers":{}}')

    def test_egm_settings_are_read_only_rules_for_plugin(self):
        rules = rx.egm_settings(Path("/opt/egm"))["permissions"]["allow"]
        self.assertIn("Read(//opt/egm/agents/**)", rules)
        self.assertTrue(all(r.split("(")[0] in {"Read", "Glob", "Grep"} for r in rules))

    def test_plan_runs(self):
        self.assertEqual(rx.plan_runs(["egm", "fresh"], 2, 1), [("egm", 1), ("fresh", 1), ("fresh", 2)])

    def test_prompt_template_has_placeholder(self):
        t = (rx.PROMPTS / "in_context_turn1.txt").read_text()
        self.assertIn("{DESIGN_DOC}", t)

    def test_toy_doc_exists(self):
        self.assertTrue((rx.TOY / rx.DOC).exists())


class EndToEndWithFakeClaude(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.fake = t / "fake-claude"
        self.fake.write_text(FAKE_CLAUDE)
        self.fake.chmod(self.fake.stat().st_mode | stat.S_IEXEC)
        self.log = t / "calls.jsonl"
        os.environ["FAKE_CLAUDE_LOG"] = str(self.log)
        self.plugin = t / "egm-plugin"
        self.plugin.mkdir()
        self.out = t / "out"

    def tearDown(self):
        os.environ.pop("FAKE_CLAUDE_LOG", None)
        self.tmp.cleanup()

    def run_main(self, *extra):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = rx.main(["--claude", str(self.fake), "--out", str(self.out),
                            "--egm-plugin-dir", str(self.plugin), *extra])
        return code, buf.getvalue()

    def calls(self):
        return [json.loads(l) for l in self.log.read_text().splitlines()]

    def test_all_arms(self):
        code, out = self.run_main("--runs", "1", "--parallel", "2")
        self.assertEqual(code, 0, out)
        for name in ["egm-1", "fresh-1", "in-context-1"]:
            self.assertTrue((self.out / name / "review.md").exists(), name)
        # EGM: consolidated report becomes review.md, stage report kept separately
        self.assertIn("get_url", (self.out / "egm-1" / "review.md").read_text())
        self.assertTrue((self.out / "egm-1" / "stage-reports" / "zoom_out_report.md").exists())
        settings = json.loads((self.out / "egm-1" / "workspace" / ".claude" / "settings.json").read_text())
        self.assertTrue(settings["permissions"]["allow"])
        # in-context: two calls, second resumes the first session
        ctx = [c for c in self.calls() if "/in-context-1/" in c["cwd"]]
        self.assertEqual(len(ctx), 2)
        self.assertEqual(ctx[1]["args"][ctx[1]["args"].index("--resume") + 1], "sess-123")
        self.assertIn("Complex Event Pipeline", ctx[0]["args"][ctx[0]["args"].index("-p") + 1])
        # EGM call loads the plugin and may spawn subagents; others may not
        egm = next(c for c in self.calls() if "/egm-1/" in c["cwd"])
        self.assertIn("--plugin-dir", egm["args"])
        self.assertIn("Agent", egm["args"][egm["args"].index("--allowedTools") + 1])
        fresh = next(c for c in self.calls() if "/fresh-1/" in c["cwd"])
        self.assertNotIn("Agent", fresh["args"][fresh["args"].index("--allowedTools") + 1])
        # scoring ran and the manifest was written
        self.assertTrue((self.out / "results.md").exists())
        self.assertTrue((self.out / "report.html").exists())
        manifest = json.loads((self.out / "manifest.json").read_text())
        self.assertEqual(manifest["claude_version"], "9.9.9 (Fake Claude)")
        self.assertTrue(all(r["ok"] for r in manifest["runs"].values()))

    def test_in_context_workspace_starts_without_the_doc(self):
        ws = rx.prepare_workspace(self.out / "probe", drop_doc=True)
        self.assertFalse((ws / rx.DOC).exists())
        self.assertTrue((ws / "shortener" / "api.py").exists())

    def test_missing_review_is_reported_not_raised(self):
        # a fake that writes nothing
        self.fake.write_text("#!/bin/sh\n[ \"$1\" = --version ] && echo v && exit 0\n"
                             "echo '{\"session_id\":\"s\"}'\n")
        code, out = self.run_main("--arms", "fresh", "--runs", "1")
        self.assertEqual(code, 2)
        self.assertIn("no review file was written", out)

    def test_cli_failure_is_recorded(self):
        self.fake.write_text("#!/bin/sh\n[ \"$1\" = --version ] && echo v && exit 0\necho boom >&2; exit 3\n")
        code, out = self.run_main("--arms", "fresh", "--runs", "1")
        self.assertEqual(code, 2)
        run = json.loads((self.out / "fresh-1" / "run.json").read_text())
        self.assertIn("exited 3", run["note"])

    def test_dry_run_calls_nothing(self):
        code, out = self.run_main("--dry-run", "--runs", "1")
        self.assertEqual(code, 0)
        self.assertIn("[dry-run]", out)
        self.assertFalse(self.log.exists())

    def test_unknown_arm_rejected(self):
        with self.assertRaises(SystemExit), redirect_stdout(io.StringIO()):
            import contextlib
            with contextlib.redirect_stderr(io.StringIO()):
                rx.main(["--arms", "nope"])


class ToyApp(unittest.TestCase):
    """The toy app the design doc describes really behaves the way the planted flaws assume."""

    def setUp(self):
        sys.path.insert(0, str(rx.TOY))
        for m in [m for m in sys.modules if m.startswith("shortener")]:
            del sys.modules[m]

    def tearDown(self):
        sys.path.remove(str(rx.TOY))

    def test_store_has_get_not_get_url(self):
        from shortener.store import LinkStore
        self.assertTrue(hasattr(LinkStore, "get"))
        self.assertFalse(hasattr(LinkStore, "get_url"))

    def test_slugs_use_sha256(self):
        import hashlib
        from shortener import slugs
        src = Path(slugs.__file__).read_text()
        self.assertIn("sha256", src)
        self.assertNotIn("md5", src.lower())
        self.assertEqual(len(slugs.make_slug("https://example.com")), 7)
        self.assertTrue(hashlib)  # imported for clarity

    def test_resolve_round_trip(self):
        from shortener import api
        slug = api.create_link("https://example.com/a")
        self.assertEqual(api.resolve(slug), (302, "https://example.com/a"))
        self.assertEqual(api.resolve("missing"), (404, None))


if __name__ == "__main__":
    unittest.main()
