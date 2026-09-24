"""Synthetic tests for the authorized-stage handoff publisher."""
from __future__ import annotations

import importlib.util
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("stage_handoff", Path(__file__).resolve().parents[1] / "tools" / "stage_handoff.py")
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
handoff = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(handoff)


class HandoffTests(unittest.TestCase):
    def test_public_path_allowlist(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ("CHATGPT_REVIEW.md", "docs/evidence.md", "reports/runs/r12345/GATE.json", "src/mosei/model.py", "reports/data_contract/contract_summary.json"):
                p = root / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text("safe", encoding="utf-8")
                self.assertEqual(handoff.public_path(name, "r12345", "S01", root), p)
            report = root / "reports/engineering/s00e_public_tree_scan.json"
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text("{}", encoding="utf-8")
            self.assertEqual(handoff.public_path("reports/engineering/s00e_public_tree_scan.json",
                                                "r12345", "S00E", root), report)
            with self.assertRaises(handoff.HandoffError):
                handoff.public_path("reports/engineering/s00e_public_tree_scan.json",
                                    "r12345", "S01", root)

    def test_public_path_rejects_private_and_escape(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ("../escape.md", "E题数据/secret.pkl", "configs/paths.local.json", "reports/runs/other/GATE.json", "reports/runs/r12345/private/log.txt", "x.mp4"):
                with self.subTest(name=name), self.assertRaises(handoff.HandoffError):
                    handoff.public_path(name, "r12345", "S01", root)

    def test_public_scan_rejects_raw_id_and_sample_csv(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "report.md"; p.write_text("clip abcdef" + "$_$" + "12", encoding="utf-8")
            self.assertIn("raw_sample_id", handoff.scan_public(p))
            p = Path(temp) / "rows.csv"; p.write_text("sample_id,label\na,1\n", encoding="utf-8")
            self.assertIn("sample_level_csv_columns", handoff.scan_public(p))

    def test_public_scan_rejects_test_distribution_and_raw_text_array(self):
        self.assertIn("test_distribution_key:histogram", handoff.scan_json({"test": {"histogram": [1, 2]}}))
        self.assertIn("test_distribution_key:mean", handoff.scan_json({"test_split": {"mean": 0.1}}))
        self.assertIn("raw_text_array", handoff.scan_json({"raw_text": ["private sentence"]}))
        self.assertIn("sample_level_label_array", handoff.scan_json({"classification_labels": [0, 1]}))
        self.assertEqual(handoff.scan_json({"test": {"fields": {"labels": {"shape": [5]}}}}), [])

    def test_task_authorization_and_gate_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "TASK_SPEC.md").write_text("task_id: S01_EXAMPLE\nstatus: ACTIVE\nresearch_authorized: true\n", encoding="utf-8")
            run = root / "reports/runs/r12345"; run.mkdir(parents=True)
            (run / "RUN.json").write_text(json.dumps({"task_id": "S01_EXAMPLE", "data_kind": "official"}), encoding="utf-8")
            (run / "GATE.json").write_text(json.dumps({"passed": False, "status": "FAIL", "summary": {"FAIL": 1}}), encoding="utf-8")
            (run / "TEST_RESULTS.json").write_text(json.dumps({"exit_code": 0, "passed": 1, "failed": 0}), encoding="utf-8")
            with self.assertRaisesRegex(handoff.HandoffError, "Gate"):
                handoff.validate_run({"stage": "S01", "run_id": "r12345", "task_id": "S01_EXAMPLE", "public_files": []}, root)
            (root / "TASK_SPEC.md").write_text("task_id: S01_EXAMPLE\nstatus: ACTIVE\nresearch_authorized: false\n", encoding="utf-8")
            with self.assertRaisesRegex(handoff.HandoffError, "authorize"):
                handoff.validate_run({"stage": "S01", "run_id": "r12345", "task_id": "S01_EXAMPLE", "public_files": []}, root)

    def test_synthetic_run_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / "TASK_SPEC.md").write_text("task_id: S01_EXAMPLE\nstatus: ACTIVE\nresearch_authorized: true\n", encoding="utf-8")
            run = root / "reports/runs/r12345"; run.mkdir(parents=True)
            (run / "RUN.json").write_text(json.dumps({"task_id": "S01_EXAMPLE", "data_kind": "synthetic"}), encoding="utf-8")
            (run / "GATE.json").write_text(json.dumps({"passed": True, "status": "PASS", "summary": {"FAIL": 0}}), encoding="utf-8")
            (run / "TEST_RESULTS.json").write_text(json.dumps({"exit_code": 0, "passed": 1, "failed": 0}), encoding="utf-8")
            with self.assertRaisesRegex(handoff.HandoffError, "Real official"):
                handoff.validate_run({"stage": "S01", "run_id": "r12345", "task_id": "S01_EXAMPLE", "public_files": []}, root)

    def test_acceptance_hash_verified(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); p = root / "reports/x.json"; p.parent.mkdir(); p.write_text("{}", encoding="utf-8")
            a = root / "acceptance.json"; a.write_text(json.dumps({"stage": "S01", "evidence": [{"path": "reports/x.json", "sha256": "0" * 64}]}), encoding="utf-8")
            with patch.object(handoff, "ROOT", root), self.assertRaisesRegex(handoff.HandoffError, "hash mismatch"):
                handoff.validate_acceptance(a, "S01")
            a.write_text(json.dumps({"stage": "S01", "evidence": [{"path": "E题数据/raw.pkl", "sha256": "0" * 64}]}), encoding="utf-8")
            with patch.object(handoff, "ROOT", root), self.assertRaisesRegex(handoff.HandoffError, "Unsafe acceptance"):
                handoff.validate_acceptance(a, "S01")

    def test_final_review_update_refreshes_acceptance_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            review = root / "CHATGPT_REVIEW.md"
            review.write_text("status: `READY`\n", encoding="utf-8")
            acceptance = root / "reports/stages/S01/acceptance.json"
            acceptance.parent.mkdir(parents=True)
            acceptance.write_text(json.dumps({"stage": "S01", "evidence": [{
                "requirement": "review", "path": "CHATGPT_REVIEW.md",
                "sha256": hashlib.sha256(review.read_bytes()).hexdigest()}]}), encoding="utf-8")
            review.write_text("status: `SUCCESS`\n", encoding="utf-8")
            with patch.object(handoff, "ROOT", root):
                with self.assertRaisesRegex(handoff.HandoffError, "hash mismatch"):
                    handoff.validate_acceptance(acceptance, "S01")
                handoff.refresh_acceptance("S01", "r12345", ["CHATGPT_REVIEW.md"])
                handoff.validate_acceptance(acceptance, "S01")

    def test_authorized_real_run_preflight(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "TASK_SPEC.md").write_text("task_id: S01_EXAMPLE\nstatus: ACTIVE\nresearch_authorized: true\n", encoding="utf-8")
            review = root / "CHATGPT_REVIEW.md"; review.write_text("# Current Review\n", encoding="utf-8")
            run = root / "reports/runs/r12345"; (run / "public").mkdir(parents=True)
            records = {"RUN.json": {"task_id": "S01_EXAMPLE", "data_kind": "official"},
                       "GATE.json": {"task_id": "S01_EXAMPLE", "run_id": "r12345",
                                     "passed": True, "status": "PASS",
                                     "summary": {"PASS": 1, "FAIL": 0, "SKIPPED": 0, "BLOCKED": 0},
                                     "items": [{"id": "X01", "status": "PASS", "evidence": ["docs/evidence.md"]}]},
                       "TEST_RESULTS.json": {"exit_code": 0, "passed": 3, "failed": 0}}
            for name, value in records.items():
                (run / name).write_text(json.dumps(value), encoding="utf-8")
            manifest = {"stage": "S01", "task_id": "S01_EXAMPLE", "run_id": "r12345", "public_files": []}
            (run / "public/HANDOFF_INPUTS.json").write_text(json.dumps(manifest), encoding="utf-8")
            acceptance = root / "reports/stages/S01/acceptance.json"; acceptance.parent.mkdir(parents=True)
            acceptance.write_text(json.dumps({"stage": "S01", "evidence": [{"path": "reports/runs/r12345/RUN.json", "sha256": hashlib.sha256((run / "RUN.json").read_bytes()).hexdigest()}]}), encoding="utf-8")
            with patch.object(handoff, "ROOT", root), patch.object(
                    handoff, "scan_tracked_public_tree", return_value={"scanned_text_files": 0, "findings": {}}):
                files, returned_run = handoff.validate_run(manifest, root)
            self.assertEqual(returned_run, run)
            self.assertIn("CHATGPT_REVIEW.md", files)
            self.assertIn("reports/runs/r12345/public/HANDOFF_INPUTS.json", files)

    def test_exact_stage_uses_explicit_pathspec(self):
        calls = []
        paths = ["CHATGPT_REVIEW.md", "reports/runs/r12345/GATE.json", "reports/stages/S01/acceptance.json"]
        def fake_git(*args, **kwargs):
            if args[:2] == ("status", "--short"):
                return " M CHATGPT_REVIEW.md"
            if args[:3] == ("diff", "--cached", "--name-only"):
                return "CHATGPT_REVIEW.md\0"
            if args[:3] == ("diff", "--cached", "--name-status"):
                return "M\tCHATGPT_REVIEW.md"
            if args[:2] == ("rev-parse", "HEAD"):
                return "a" * 40
            return ""
        def fake_command(*args, **kwargs):
            calls.append(args)
            return SimpleNamespace(returncode=0)
        with patch.object(handoff, "git", side_effect=fake_git), patch.object(handoff, "command", side_effect=fake_command), patch.object(handoff, "public_path", return_value=Path("dummy")), patch.object(handoff, "scan_public", return_value=[]), patch.object(handoff, "scan_tracked_public_tree", return_value={"scanned_text_files": 0, "findings": {}}):
            with patch.object(handoff, "verify_staged_bytes"):
                self.assertEqual(handoff.exact_stage(paths, "message"), "a" * 40)
        self.assertIn(("git", "-c", "core.autocrlf=false", "add", "--", *paths), calls)
        self.assertFalse(any("-A" in x or "--all" in x for call in calls for x in call))

    def test_porcelain_leading_status_space_is_preserved(self):
        raw = " M CHATGPT_REVIEW.md\0?? docs/S00C_SUPPORT_EVIDENCE.md\0"
        with patch.object(handoff, "command", return_value=SimpleNamespace(stdout=raw)):
            self.assertEqual(handoff.worktree_changed_paths(),
                             {"CHATGPT_REVIEW.md", "docs/S00C_SUPPORT_EVIDENCE.md"})

    def test_index_records_live_ref_and_exact_metadata(self):
        value = handoff.latest_index("S01", "S01_EXAMPLE", "r12345", "a" * 40, "b" * 40, {"url": "https://example.test"}, ["docs/evidence.md"])
        self.assertEqual(value["metadata_commit"], "b" * 40)
        self.assertEqual(value["branch_head"]["ref"], "refs/heads/codex/mosei-auto")
        self.assertFalse(value["next_stage_authorized"])

    def test_already_indexed_run_stops_before_git_write(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run = root / "reports/runs/r12345/public"; run.mkdir(parents=True)
            manifest_path = run / "HANDOFF_INPUTS.json"
            manifest_path.write_text(json.dumps({"stage": "S01", "task_id": "S01_EXAMPLE", "run_id": "r12345", "public_files": []}), encoding="utf-8")
            state = root / "state"; state.mkdir(); (state / "LATEST_RUN.json").write_text(json.dumps({"run_id": "r12345"}), encoding="utf-8")
            with patch.object(handoff, "ROOT", root), patch.object(handoff, "verify_workspace", return_value="a" * 40), patch.object(handoff, "exact_stage", side_effect=AssertionError("Git write forbidden")):
                with self.assertRaisesRegex(handoff.HandoffError, "already indexed"):
                    handoff.publish(manifest_path)

    def test_legacy_release_entry_is_disabled(self):
        spec = importlib.util.spec_from_file_location("mosei_flow_legacy", Path(__file__).resolve().parents[1] / "tools" / "mosei_flow.py")
        legacy = importlib.util.module_from_spec(spec); spec.loader.exec_module(legacy)
        with patch.object(sys, "argv", ["mosei_flow.py", "publish"]):
            with self.assertRaisesRegex(SystemExit, "Legacy publish is disabled"):
                legacy.main()

    def test_current_index_points_to_existing_public_evidence(self):
        root = Path(__file__).resolve().parents[1]
        value = json.loads((root / "state/LATEST_RUN.json").read_text(encoding="utf-8"))
        self.assertEqual(value["branch_head"]["ref"], "refs/heads/codex/mosei-auto")
        self.assertTrue((root / value["review_path"]).is_file())
        self.assertTrue(all((root / name).is_file() and not handoff.forbidden_path(name) for name in value["core_public_evidence_paths"]))
        self.assertFalse(value["next_stage_authorized"])


if __name__ == "__main__":
    unittest.main()
