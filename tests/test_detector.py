"""Tests for model-deprecation-detector.

The fixture tests are the contract: fixtures/v1/sample-app must always scan
to fixtures/v1/expected.json at the pinned scan date 2026-11-13 against the
bundled lifecycle table. Run: python -m unittest discover -s tests -v
"""

import json
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from model_deprecation_detector.cli import build_report, main  # noqa: E402
from model_deprecation_detector.lifecycle import classify, load_table  # noqa: E402
from model_deprecation_detector.scanner import scan  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "fixtures" / "v1" / "sample-app"
EXPECTED = json.loads((ROOT / "fixtures" / "v1" / "expected.json").read_text())
PINNED = date(2026, 11, 13)


class TestClassify(unittest.TestCase):
    def test_retired_after_shutdown(self):
        entry = {"deprecated_date": "2025-01-21", "shutdown_date": "2025-07-21",
                 "replacement_candidates": ["claude-opus-4-8"], "source_url": "x"}
        self.assertEqual(classify(entry, PINNED)["status_to"], "retired")

    def test_deprecated_before_shutdown(self):
        entry = {"deprecated_date": "2026-09-30", "shutdown_date": "2026-11-30",
                 "replacement_candidates": ["claude-sonnet-5-5"], "source_url": "x"}
        verdict = classify(entry, PINNED)
        self.assertEqual(verdict["status_to"], "deprecated")
        self.assertEqual(verdict["successor"], "claude-sonnet-5-5")

    def test_announced_future_deprecation(self):
        entry = {"deprecated_date": "2027-01-01", "shutdown_date": "2027-07-01",
                 "replacement_candidates": [], "source_url": "x"}
        self.assertEqual(classify(entry, PINNED)["status_to"], "announced")

    def test_missing_entry_is_not_a_clean_bill(self):
        verdict = classify(None, PINNED)
        self.assertEqual(verdict["status_to"], "no-lifecycle-entry")
        self.assertIsNone(verdict["successor"])


class TestFixtureScan(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = build_report(FIXTURE, PINNED, load_table())

    def test_files_scanned(self):
        self.assertEqual(self.report["files_scanned"], EXPECTED["files_scanned"])

    def test_summary_counts(self):
        s = self.report["summary"]
        self.assertEqual(s["distinct_model_ids"], EXPECTED["distinct_model_ids"])
        self.assertEqual(s["total_references"], EXPECTED["total_references"])

    def test_status_grouping_matches_expected(self):
        grouped = {}
        for item in self.report["references"]:
            grouped.setdefault(item["lifecycle"]["status_to"], []).append(item["model_id"])
        for status, ids in EXPECTED["by_status"].items():
            key = "no-lifecycle-entry" if status == "no_lifecycle_entry" else status
            self.assertEqual(sorted(grouped.get(key, [])), sorted(ids), status)

    def test_notices_match_expected(self):
        got = {(n["model_id"], n["status_to"], n["sunset_date"], n["successor"])
               for n in self.report["notices"]}
        want = {(n["model_id"], n["status_to"], n["sunset_date"], n["successor"])
                for n in EXPECTED["notices"]}
        self.assertEqual(got, want)

    def test_locations_are_real(self):
        for item in self.report["references"]:
            for loc in item["locations"]:
                lines = (FIXTURE / loc["file"]).read_text().splitlines()
                self.assertIn(item["model_id"], lines[loc["line"] - 1])

    def test_notice_schema_fields(self):
        required = {"provider", "model_id", "status_from", "status_to",
                    "sunset_date", "successor", "price_change",
                    "changelog_url", "source_feed", "locations"}
        for notice in self.report["notices"]:
            self.assertTrue(required.issubset(notice.keys()))
            # Pricing is never invented by this tool.
            self.assertIsNone(notice["price_change"])


class TestScanner(unittest.TestCase):
    def test_clean_file_has_no_references(self):
        refs, _ = scan(FIXTURE)
        self.assertFalse(any(r["file"].endswith("clean.py") for r in refs))

    def test_no_duplicate_reference_lines(self):
        refs, _ = scan(FIXTURE)
        keys = [(r["file"], r["line"], r["model_id"]) for r in refs]
        self.assertEqual(len(keys), len(set(keys)))


class TestCli(unittest.TestCase):
    def test_exit_1_on_retired_by_default(self):
        self.assertEqual(main([str(FIXTURE), "--today", "2026-11-13",
                               "--format", "json"]), 1)

    def test_exit_0_with_fail_on_never(self):
        self.assertEqual(main([str(FIXTURE), "--today", "2026-11-13",
                               "--fail-on", "never", "--format", "feed"]), 0)

    def test_exit_2_on_missing_dir(self):
        self.assertEqual(main(["/nonexistent-dir-xyz"]), 2)


if __name__ == "__main__":
    unittest.main()
