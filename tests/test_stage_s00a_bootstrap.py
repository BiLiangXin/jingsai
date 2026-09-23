"""Synthetic engineering tests. No competition file is opened."""
import csv
import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("mosei_flow", Path(__file__).resolve().parents[1] / "tools" / "mosei_flow.py")
flow = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(flow)


class BootstrapTests(unittest.TestCase):
    def test_t01_repo_root_detection(self):
        self.assertEqual(flow.ROOT, Path(__file__).resolve().parents[1])

    def test_t02_expected_baseline_sha(self):
        with patch.object(flow, "run", return_value=type("R", (), {"stdout": flow.BASELINE + "\trefs/heads/main", "returncode": 0})()):
            self.assertEqual(flow.verify_baseline()["status"], "PASS")
        with patch.object(flow, "run", return_value=type("R", (), {"stdout": "a" * 40, "returncode": 0})()):
            self.assertEqual(flow.verify_baseline()["status"], "BLOCKED")

    def test_t03_raw_data_gitignored(self):
        self.assertIn("E题数据/", (flow.ROOT / ".gitignore").read_text(encoding="utf-8"))
        self.assertEqual(flow.run("git", "check-ignore", "-q", "E题数据/synthetic.pkl").returncode, 0)

    def test_t04_raw_data_rejected_from_package(self):
        self.assertTrue(flow.forbidden_path("E题数据/test.pkl"))

    def test_t05_secret_detection(self):
        self.assertIn("secret_pattern", flow.scan_text("token = " + "x" * 24))

    def test_t06_private_windows_path_detection(self):
        self.assertIn("private_windows_path", flow.scan_text("C:" + chr(92) + "Users" + chr(92) + "alice" + chr(92) + "file"))

    def test_t07_selective_migration_manifest(self):
        path = flow.ROOT / "reports" / "bootstrap" / "MIGRATION_INVENTORY.csv"
        with path.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertTrue(rows)
        self.assertEqual({"source", "destination", "action", "reason", "risk_flags", "sanitized"}, set(rows[0]))
        self.assertTrue(all(r["action"] in {"MIGRATE", "RECREATE", "SKIP", "REVIEW_REQUIRED"} for r in rows))
        self.assertFalse(any(r["action"] == "MIGRATE" and flow.forbidden_path(r["source"]) for r in rows))

    def test_t08_run_archive_generation(self):
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp) / "run"
            flow.archive(run_dir, {"run_id": "synthetic"}, [flow.ROOT / "TASK_SPEC.md"])
            self.assertEqual(json.loads((run_dir / "RUN.json").read_text())["run_id"], "synthetic")
            self.assertTrue((run_dir / "MANIFEST.json").exists())

    def test_t09_sha256_generation(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "x"
            path.write_bytes(b"abc")
            self.assertEqual(flow.sha256(path), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")

    def test_t10_review_zip_generation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "safe.md").write_text("safe", encoding="utf-8")
            result = flow.make_review_zip(root / "out.zip", [root / "safe.md"], root)
            self.assertEqual(result["members"], ["safe.md"])

    def test_t11_review_zip_forbidden_scan(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "bad.pkl").write_bytes(b"synthetic")
            with self.assertRaises(ValueError):
                flow.make_review_zip(root / "out.zip", [root / "bad.pkl"], root)
            self.assertFalse((root / "out.zip").exists())

    def test_t12_publish_dry_run_idempotent(self):
        self.assertEqual(flow.publish_dry_run("r", {"codex-run-r"}, True)["create_release"], False)

    def test_t13_same_run_no_duplicate_release(self):
        self.assertEqual(flow.publish_dry_run("r", {"codex-run-r"}, True)["status"], "EXISTS")

    def test_t14_no_change_no_commit(self):
        self.assertFalse(flow.publish_dry_run("r", set(), False)["create_commit"])

    def test_t15_gate_status(self):
        passed = flow.gate([{"id": "x", "name": "x", "status": "PASS", "evidence": ["file"], "details": "ok"}])
        self.assertTrue(passed["passed"])
        self.assertFalse(flow.gate([{"id": "x", "name": "x", "status": "BLOCKED", "evidence": [], "details": "blocked"}])["passed"])
        with self.assertRaises(ValueError):
            flow.gate([{"id": "x", "name": "x", "status": "PASS", "evidence": [], "details": "bad"}])

    def test_t16_chatgpt_review_generation(self):
        path = flow.ROOT / "CHATGPT_REVIEW.md"
        self.assertIn("# Current Review", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
