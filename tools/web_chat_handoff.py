"""Create a local, scanned ZIP for a project reply; never publish it."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from mosei_flow import forbidden_path, scan_text
from stage_handoff import PUBLIC_SUFFIXES, RAW_ID, scan_json, scan_public

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path("reports/web_chat_handoffs")
ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{5,79}\Z")
FIELDS = {"stage", "status", "summary", "changes", "tests", "blockers", "next_actions", "data_kind", "metrics_file"}


class BundleError(ValueError):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def source_bytes(root: Path, relative: str) -> bytes:
    path = PurePosixPath(relative)
    if (path.is_absolute() or ".." in path.parts or "\\" in relative or
            not path.parts or forbidden_path(relative) or
            {part.lower() for part in path.parts} & {"private", "artifacts"} or
            path.suffix.lower() not in PUBLIC_SUFFIXES):
        raise BundleError(f"Unsafe source path: {relative}")
    target = root / relative
    if not target.is_file() or target.is_symlink() or not target.resolve().is_relative_to(root.resolve()):
        raise BundleError(f"Missing or nonlocal source: {relative}")
    issues = scan_public(target)
    if issues:
        raise BundleError(f"Unsafe source {relative}: {issues}")
    return target.read_bytes()


def validate_response(response: dict) -> None:
    if set(response) != FIELDS or response["status"] not in {"completed", "blocked", "failed"}:
        raise BundleError("Invalid response fields or status")
    if response["data_kind"] not in {"official", "synthetic", "none"}:
        raise BundleError("Invalid data_kind")
    if not all(isinstance(response[key], list) for key in ("changes", "tests", "blockers", "next_actions")):
        raise BundleError("Response lists are invalid")
    if not isinstance(response["stage"], str) or not isinstance(response["summary"], str):
        raise BundleError("Response stage or summary is invalid")
    encoded = json_bytes(response).decode("utf-8")
    issues = scan_text(encoded) + scan_json(response)
    if RAW_ID.search(encoded):
        issues.append("raw_sample_id")
    if issues:
        raise BundleError(f"Unsafe response: {issues}")


def create_bundle(root: Path, bundle_id: str, response: dict, includes: list[str]) -> dict:
    if not ID_PATTERN.fullmatch(bundle_id):
        raise BundleError("Invalid bundle ID")
    validate_response(response)
    if len(set(includes)) != len(includes):
        raise BundleError("Duplicate source path")
    members: dict[str, bytes] = {
        "response.json": json_bytes(response),
        "README.md": ("# Web Chat handoff\n\nUpload this ZIP to Chat and ask it to review "
                      "`response.json` and the included public evidence. "
                      "The manifest lists every file and its SHA256. "
                      "This package does not authorize a new research stage.\n").encode("utf-8"),
    }
    for relative in includes:
        if relative in members or relative == "MANIFEST.json":
            raise BundleError(f"Reserved member name: {relative}")
        members[relative] = source_bytes(root, relative)
    manifest = {"schema_version": 1, "bundle_id": bundle_id,
                "files": [{"path": name, "sha256": digest(data), "size_bytes": len(data)}
                          for name, data in sorted(members.items())]}
    members["MANIFEST.json"] = json_bytes(manifest)
    output_dir = root / OUTPUT / bundle_id
    if output_dir.exists():
        raise BundleError("Bundle ID already exists; no files were overwritten")
    output_dir.mkdir(parents=True)
    target = output_dir / f"web-chat-handoff-{bundle_id}.zip"
    try:
        with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in sorted(members.items()):
                archive.writestr(name, data)
        with zipfile.ZipFile(target) as archive:
            if sorted(archive.namelist()) != sorted(members):
                raise BundleError("ZIP member list mismatch")
            for entry in manifest["files"]:
                data = archive.read(entry["path"])
                if digest(data) != entry["sha256"] or len(data) != entry["size_bytes"]:
                    raise BundleError(f"ZIP integrity failure: {entry['path']}")
            if json.loads(archive.read("MANIFEST.json")) != manifest:
                raise BundleError("ZIP manifest mismatch")
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return {"path": str(target.resolve()), "sha256": digest(target.read_bytes()),
            "size_bytes": target.stat().st_size, "member_count": len(members)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--response", type=Path, required=True, help="UTF-8 result JSON")
    parser.add_argument("--include", action="append", default=[], help="Exact public repository path")
    parser.add_argument("--bundle-id", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    args = parser.parse_args()
    response = json.loads(args.response.read_text(encoding="utf-8"))
    print(json.dumps(create_bundle(ROOT, args.bundle_id, response, args.include), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
