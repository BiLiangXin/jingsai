"""Synthetic safety and integrity checks for local web Chat handoffs."""
import json
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from web_chat_handoff import BundleError, create_bundle  # noqa: E402


RESPONSE = {"stage": "ENGINEERING_HANDOFF", "status": "completed", "summary": "Done",
            "changes": ["Safe file packaged"], "tests": ["Synthetic test passed"],
            "blockers": [], "next_actions": [], "data_kind": "synthetic", "metrics_file": None}


def test_bundle_manifest_and_no_overwrite(tmp_path):
    (tmp_path / "AGENTS.md").write_text("Public instructions\n", encoding="utf-8")
    result = create_bundle(tmp_path, "sample-001", RESPONSE, ["AGENTS.md"])
    with zipfile.ZipFile(result["path"]) as archive:
        manifest = json.loads(archive.read("MANIFEST.json"))
        assert {row["path"] for row in manifest["files"]} == {"README.md", "response.json", "AGENTS.md"}
        assert json.loads(archive.read("response.json")) == RESPONSE
    assert result["member_count"] == 4
    with pytest.raises(BundleError, match="already exists"):
        create_bundle(tmp_path, "sample-001", RESPONSE, ["AGENTS.md"])


@pytest.mark.parametrize("name,content", [
    ("data.pkl", "public"),
    ("private/note.md", "public"),
    ("sample.json", '{"sample_level_labels":[1,2]}'),
    ("path.md", "C:\\Users\\alice\\private\\file"),
])
def test_rejects_unsafe_inputs(tmp_path, name, content):
    target = tmp_path / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    with pytest.raises(BundleError):
        create_bundle(tmp_path, "sample-002", RESPONSE, [name])
    assert not (tmp_path / "reports/web_chat_handoffs/sample-002").exists()


def test_rejects_sample_id_in_response(tmp_path):
    response = {**RESPONSE, "summary": "sampleclip$_$123 must remain private"}
    with pytest.raises(BundleError, match="raw_sample_id"):
        create_bundle(tmp_path, "sample-003", response, [])
