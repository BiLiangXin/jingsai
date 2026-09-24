"""Read-only safety gate for an S01 activation or aggregate-results publication.

Run from the official repository. Never stages, commits, pushes, publishes a
Release, reads competition data, or consumes execution authorization. The only
write is a new JSON report outside the repository. A publication manifest uses
base_commit, publication_files, files[{path,sha256,size_bytes}], and explicit
hash_exclusions{paths,reason}; exclusions remain scanned and Git-bound.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import io
import json
import posixpath
import re
import stat
import struct
import subprocess
import sys
import warnings
import zipfile
import zlib
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree

sys.dont_write_bytecode = True
BASELINE = "71524473e915412ef823d9ad8dcb5928c4eeb2ca"
ORIGIN = "https://github.com/BiLiangXin/jingsai.git"
BRANCH = "codex/mosei-auto"
FROZEN = ("docs/research/R01", "research/r01", "src/mosei/data")
SUFFIXES = {".md", ".json", ".csv", ".py", ".toml", ".yaml", ".yml"}
REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024)
LEGACY_PROBLEM_ASSETS = {
    "docs/assets/image1.png": "f2f2acba7f0d566bd3f77e7f6a8f6cf1effd168eb2f3d675206a951c01e64e7b",
    "docs/assets/image2.png": "3c512a360a6b0684f00aee5a27af1bdcace957ebc21191556e7f74648cf7287a",
    "复杂场景下多模态情感识别的数学建模与算法设计.docx":
        "38cec978723bff36ab945fa98f6454558bb9084e2cd01d814dd6e38ab4b4c336",
}


class PublicationCheckError(ValueError):
    pass


def need(value, message):
    if not value:
        raise PublicationCheckError(message)


def git(root, *args, input_bytes=None):
    result = subprocess.run(
        ["git", "--no-optional-locks", *args], cwd=root, input=input_bytes,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90,
    )
    need(result.returncode == 0, "Git read failed: " + " ".join(args[:2]))
    return result.stdout


def unique_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, "Duplicate JSON key")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(
                          PublicationCheckError("Nonfinite JSON number")))


def safe_relative(relative):
    need(isinstance(relative, str) and relative, "Empty or non-string path")
    posix = PurePosixPath(relative)
    need(not posix.is_absolute() and ".." not in posix.parts and
         ":" not in relative and "\\" not in relative and
         posix.as_posix() == relative and "\x00" not in relative,
         "Noncanonical or escaping manifest path")
    return posix


def no_redirect(path):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        if part.exists():
            need(not part.is_symlink() and
                 not (getattr(part.lstat(), "st_file_attributes", 0) & REPARSE),
                 "Symlink or reparse point rejected")


def read_public(root, relative):
    safe_relative(relative)
    path = root / relative
    no_redirect(path)
    need(path.is_file() and path.resolve().is_relative_to(root),
         "Missing or escaping public file: " + relative)
    need(path.stat().st_size <= 1024 * 1024,
         "Oversize public file: " + relative)
    return path.read_bytes()


def names(raw):
    return {part.decode("utf-8") for part in raw.split(b"\0") if part}


def verify_png(blob, scan_text, raw_id):
    """Verify actual PNG chunks/CRC, Pillow decode, and textual metadata.

    This is not OCR: the known problem illustration may visibly contain its
    own explanatory ID/label/transcript. No image content is exported here.
    """
    need(blob.startswith(b"\x89PNG\r\n\x1a\n"), "Legacy PNG signature mismatch")
    offset, chunks, ended = 8, 0, False
    while offset < len(blob):
        need(offset + 12 <= len(blob), "Truncated PNG chunk")
        length = struct.unpack(">I", blob[offset:offset + 4])[0]
        kind = blob[offset + 4:offset + 8]
        end = offset + 12 + length
        need(end <= len(blob) and kind.isalpha(), "Unsafe PNG chunk")
        payload = blob[offset + 8:offset + 8 + length]
        crc = struct.unpack(">I", blob[end - 4:end])[0]
        need(zlib.crc32(kind + payload) & 0xffffffff == crc, "PNG CRC mismatch")
        chunks += 1
        if kind == b"IEND":
            need(length == 0 and end == len(blob), "PNG trailing payload rejected")
            ended = True
            break
        offset = end
    need(ended, "PNG IEND missing")
    from PIL import Image
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(blob)) as img:
            need(img.format == "PNG" and 0 < img.width * img.height <= 50_000_000,
                 "Unexpected PNG format or dimensions")
            width, height = img.size
            metadata = dict(img.info)
            img.verify()
        with Image.open(io.BytesIO(blob)) as img:
            img.load()
    metadata_findings = []
    illustrative_id_metadata = False
    text_fields = 0
    for key, value in metadata.items():
        if isinstance(value, bytes):
            text = value.decode("utf-8", errors="replace")
        elif isinstance(value, str):
            text = value
        else:
            continue
        text_fields += 1
        metadata_findings.extend(scan_text(str(key) + "\n" + text))
        illustrative_id_metadata |= bool(raw_id.search(text))
    need(not metadata_findings, "Unsafe legacy PNG textual metadata")
    return dict(format="PNG", width=width, height=height, png_chunk_count=chunks,
                png_crc_verified=True, pillow_verify_and_decode=True,
                textual_metadata_fields_scanned=text_fields,
                illustrative_id_detected_in_metadata=illustrative_id_metadata,
                pixel_ocr_performed=False)


def verify_docx(blob, scan_text, raw_id):
    """Inspect every ZIP member without extracting any file to the worktree."""
    need(blob.startswith(b"PK\x03\x04"), "DOCX ZIP signature mismatch")
    xml_count, image_count, raw_id_present = 0, 0, False
    members = []
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        infos = archive.infolist()
        filenames = [info.filename for info in infos]
        need(len(filenames) == len(set(filenames)) == len({s.casefold() for s in filenames}),
             "Duplicate DOCX member names")
        need(len(infos) <= 1000 and sum(info.file_size for info in infos) <= 32 * 1024 * 1024,
             "DOCX expansion limit")
        need({"[Content_Types].xml", "word/document.xml"} <= set(filenames),
             "Required DOCX parts missing")
        need(archive.testzip() is None, "DOCX CRC failure")
        for info in infos:
            rel = info.filename
            posix = safe_relative(rel)
            lowered = rel.lower()
            need(not (info.flag_bits & 1) and not stat.S_ISLNK(info.external_attr >> 16),
                 "Encrypted or linked DOCX member")
            need(not any(part in lowered for part in
                         ("vbaproject", "activex", "embeddings/", "customui/")),
                 "DOCX active or embedded payload")
            need(not scan_text(rel) and not raw_id.search(rel), "Unsafe DOCX member filename")
            member = archive.read(info)
            if posix.suffix.lower() in (".xml", ".rels") or posix.name == ".rels":
                text = member.decode("utf-8-sig")
                need(not re.search(r"<!DOCTYPE|<!ENTITY", text, re.I), "XML DTD/entity rejected")
                need(not re.search(r"macroEnabled|vbaProject|application/x-msdownload", text, re.I),
                     "Active DOCX content type rejected")
                element = ElementTree.fromstring(text)
                need(not scan_text(text), "Unsafe legacy DOCX XML text")
                raw_id_present |= bool(raw_id.search(text))
                for node in element.iter():
                    tag = node.tag.rsplit("}", 1)[-1]
                    if tag == "Relationship":
                        target = node.attrib.get("Target", "")
                        if node.attrib.get("TargetMode") == "External":
                            need(bool(re.match(r"https?://", target, re.I)),
                                 "Unsafe external DOCX relationship")
                        else:
                            need(bool(target) and not target.startswith(("/", "\\")) and
                                 ":" not in target and "\\" not in target,
                                 "Unsafe internal DOCX relationship")
                            base = str(posix.parent.parent) if posix.parent.name == "_rels" else str(posix.parent)
                            linked = posixpath.normpath(posixpath.join(base, target.split("#", 1)[0]))
                            need(linked != ".." and not linked.startswith("../"),
                                 "Escaping internal DOCX relationship")
                    if tag == "instrText":
                        need(not re.search(r"\b(?:DDEAUTO|DDE|INCLUDETEXT|INCLUDEPICTURE)\b",
                                           node.text or "", re.I), "Active DOCX field rejected")
                xml_count += 1
            elif posix.suffix.lower() == ".png" and lowered.startswith("word/media/"):
                verify_png(member, scan_text, raw_id)
                expected = LEGACY_PROBLEM_ASSETS.get("docs/assets/" + posix.name)
                need(expected is not None and hashlib.sha256(member).hexdigest() == expected,
                     "Unrecognized embedded problem image")
                image_count += 1
            else:
                raise PublicationCheckError("Unrecognized or executable DOCX member type")
            members.append(dict(path=rel, size_bytes=len(member),
                                sha256=hashlib.sha256(member).hexdigest()))
    return dict(format="DOCX", member_count=len(members), xml_and_relationship_parts_scanned=xml_count,
                image_parts_verified=image_count, crc_verified=True, member_paths_safe=True,
                macros_or_executable_embeddings=False, illustrative_id_detected_in_xml=raw_id_present,
                member_fingerprints=members)


def verify_legacy_problem_asset(root, rel, work, index, scan_text, raw_id):
    need(rel in LEGACY_PROBLEM_ASSETS, "Unrecognized legacy binary")
    baseline = git(root, "show", BASELINE + ":" + rel)
    expected = LEGACY_PROBLEM_ASSETS[rel]
    need(hashlib.sha256(baseline).hexdigest() == expected and
         work == index == baseline, "Legacy problem asset changed from exact baseline bytes")
    details = verify_png(work, scan_text, raw_id) if rel.endswith(".png") else verify_docx(work, scan_text, raw_id)
    return dict(path=rel, sha256=expected, size_bytes=len(work), baseline_commit=BASELINE,
                index_equals_worktree_equals_baseline=True, newly_published=False,
                classification="EXISTING_PUBLIC_PROBLEM_STATEMENT_ASSET",
                legacy_problem_statement_illustration_present=rel != "docs/assets/image1.png",
                contains_authorized_new_sample_export=False, used_for_model_data_or_selection=False,
                verification=details)


def check_config(root, mode, report):
    config = unique_json(read_public(root, "configs/s01_execution.json"))
    need(config.get("protocol_freeze") == "R01-FREEZE-01" and
         config.get("core_budget") == 39 and config.get("retry_training_budget") == 0,
         "Frozen core or retry budget changed")
    need(all(config.get(key) is False for key in
             ("test_authorized", "attachment3_4_authorized", "q3_authorized")),
         "Forbidden execution scope enabled")
    need(config.get("model_seeds") == [17, 29, 43] and
         config.get("train_mask_root") == 2207 and config.get("valid_mask_root") == 1103 and
         config.get("nominal_conditions") == 96 and config.get("views") == 144 and
         config.get("random_replicates") == 3 and config.get("disabled_blocks") == ["D", "T", "L"],
         "Frozen protocol metadata changed")
    chosen = tuple(config.get(key) for key in
                   ("execution_fit_budget", "resource_walltime_cap_hours", "per_fit_walltime_cap_hours"))
    need(all(type(value) in (int, float) for value in chosen) and
         chosen in ((30, 12, 2), (24, 4, 1)), "Incorrect preauthorized budget/caps")
    need(config.get("latest_compute_finish") == "2026-09-25T18:00:00+08:00" and
         config.get("paper_submission_deadline") == "2026-09-27T00:00:00+08:00",
         "Deadline changed")
    report["execution_fit_budget"] = chosen[0]
    report["resource_walltime_cap_hours"] = chosen[1]
    report["per_fit_walltime_cap_hours"] = chosen[2]
    state = unique_json(read_public(root, "state/LATEST_RESEARCH.json"))
    if mode == "activation":
        need(config.get("training_authorized") is True and
             config.get("status") == "ACTIVE_AUTHORIZED" and
             config.get("owner_authorization_mode") == "PREAUTHORIZED_BY_CURRENT_USER_INSTRUCTION" and
             config.get("resource_cap_status") == "USER_PREAUTHORIZED",
             "Activation config is not explicitly preauthorized")
        need(config.get("device") == "cuda" and config.get("storage_cap_gib") == 5.0 and
             config.get("gpu_memory_guard_fraction") == .8,
             "Approved resource guards or device changed")
        campaign = config.get("campaign_id")
        need(isinstance(campaign, str) and 8 <= len(campaign) <= 128,
             "Missing campaign identity")
        need(state.get("s01_training_authorized") is True and
             state.get("campaign_id") == campaign, "Research state not bound to active campaign")
        task = read_public(root, "TASK_SPEC.md").decode("utf-8").replace("\r\n", "\n")
        need("task_id: S01_FROZEN_BASELINE_EXECUTION\n" in task and
             "s01_training_authorized: true\n" in task and
             "status: ACTIVE_AUTHORIZED\n" in task, "Wrong active task specification")
        # Import only the verifier; this does not call the training gate, native
        # journal functions, campaign claims, datasets, or any CUDA operation.
        sys.path.insert(0, str(root / "src"))
        from mosei.s01 import authorization as auth
        selected_at = datetime.datetime.fromisoformat(config["budget_decided_at"])
        need(auth.select_budget(selected_at) == chosen, "Budget selection timestamp mismatch")
        need(selected_at <= datetime.datetime.now(datetime.timezone.utc),
             "Budget selected in the future")
        report["authorized_manifest_sha256"] = auth.verify_manifest(root, campaign)
        report["campaign_id"] = campaign
        rows = unique_json(read_public(root, "docs/EXPERIMENT_REGISTER.json"))["s01_preregistered_fits"]
        need(len(rows) == len({row["trial_id"] for row in rows}) == 39 and
             all(row["status"] == "NOT_RUN" and row["metrics"] is None for row in rows),
             "Activation registry must retain39 unique unrun fits")
        report["official_model_experiments"] = "NOT_RUN"
    else:
        need(config.get("training_authorized") is False and
             state.get("s01_training_authorized") is False,
             "Results publication requires execution authority disabled")
        report["official_model_experiments"] = "READ_FROM_ACTUAL_RESULT_ARTIFACTS; NOT_INFERRED_BY_SAFETY_SCAN"
    report["training_authorized_in_config"] = config["training_authorized"]


def check(root, manifest_path, mode, report):
    root = root.resolve()
    no_redirect(root)
    need(git(root, "rev-parse", "--show-toplevel").decode().strip().replace("\\", "/").casefold()
         == str(root).replace("\\", "/").casefold(), "Not the repository root")
    need(git(root, "branch", "--show-current").decode().strip() == BRANCH, "Wrong branch")
    need(git(root, "remote", "get-url", "origin").decode().strip() == ORIGIN, "Wrong origin")
    head = git(root, "rev-parse", "HEAD").decode().strip()
    remote = git(root, "ls-remote", ORIGIN, "refs/heads/" + BRANCH).decode().split()
    need(len(remote) == 2 and remote == [head, "refs/heads/" + BRANCH],
         "Fresh remote and local HEAD differ")
    report.update(local_head=head, remote_head=remote[0], repository="BiLiangXin/jingsai", branch=BRANCH)
    no_redirect(manifest_path)
    need(manifest_path.is_file() and manifest_path.resolve().is_relative_to(root),
         "Publication manifest must be a public repository file")
    manifest_relative = manifest_path.resolve().relative_to(root).as_posix()
    manifest_raw = read_public(root, manifest_relative)
    manifest = unique_json(manifest_raw)
    need(manifest.get("base_commit") == head, "Expected publication parent differs from HEAD")
    report["base_commit"] = head
    report["publication_manifest_sha256"] = hashlib.sha256(manifest_raw).hexdigest()
    allowed = manifest["publication_files"]
    need(isinstance(allowed, list) and all(isinstance(p, str) for p in allowed) and
         len(allowed) == len(set(allowed)) == len({p.casefold() for p in allowed}),
         "Duplicate publication paths")
    need(manifest_relative in allowed, "Publication manifest must be declared")
    excluded = manifest.get("hash_exclusions", {})
    excluded_paths = excluded.get("paths", [])
    need(isinstance(excluded_paths, list) and
         len(excluded_paths) == len(set(excluded_paths)) and
         bool(excluded.get("reason")) and manifest_relative in excluded_paths,
         "Self/report hash exclusions must be explicit")
    for rel in excluded_paths:
        safe_relative(rel)
        need(rel == manifest_relative or
             (rel.startswith("reports/") and PurePosixPath(rel).suffix == ".json" and
              re.search(r"safety|publication[_-](?:check|gate)", PurePosixPath(rel).name, re.I)),
             "Only self or named safety/check reports may omit payload hashes")
    entries = manifest["files"]
    payload_paths = [row["path"] for row in entries]
    need(len(payload_paths) == len(set(payload_paths)) and
         set(payload_paths).isdisjoint(excluded_paths) and
         set(payload_paths) | set(excluded_paths) == set(allowed),
         "Manifest hashes/exclusions must exactly cover publication files")
    changed = names(git(root, "diff", "--name-only", "HEAD", "-z"))
    untracked = names(git(root, "ls-files", "--others", "--exclude-standard", "-z"))
    staged = names(git(root, "diff", "--cached", "--name-only", "-z"))
    need(changed | untracked == set(allowed), "Modified/untracked set differs from declared exact file set")
    need(staged <= set(allowed), "Unrelated staged files")
    need(not git(root, "ls-files", "--unmerged", "-z"), "Unmerged index")
    report.update(publication_file_count=len(allowed), modified_or_untracked_count=len(changed | untracked),
                  staged_count=len(staged), staged_subset_verified=True,
                  exact_staged_set_verified=staged == set(allowed))
    sys.path.insert(0, str(root / "tools"))
    from stage_handoff import scan_tracked_public_tree, scan_public_bytes, forbidden_path, scan_text, RAW_ID
    need(not set(allowed) & set(LEGACY_PROBLEM_ASSETS),
         "Legacy binary assets cannot be candidate or staged publication files")
    for rel in allowed:
        posix = safe_relative(rel)
        need(not forbidden_path(rel) and
             (posix.suffix.lower() in SUFFIXES or rel in (".gitignore", ".gitattributes")),
             "Forbidden or binary publication path: " + rel)
        blob = read_public(root, rel)
        issues = scan_public_bytes(rel, blob)
        if issues:
            report["findings"].append(dict(path=rel, surface="candidate", issues=issues))
        if rel in staged:
            need(git(root, "show", ":" + rel) == blob, "Staged/worktree bytes differ: " + rel)
    report["candidate_files_scanned"] = len(allowed)
    report["staged_equals_worktree_verified"] = True
    for row in entries:
        blob = read_public(root, row["path"])
        need(type(row["size_bytes"]) is int and len(blob) == row["size_bytes"] and
             re.fullmatch(r"[a-f0-9]{64}", row["sha256"]) and
             hashlib.sha256(blob).hexdigest() == row["sha256"],
             "Publication payload hash/size mismatch: " + row["path"])
    report["payload_hashes_verified"] = len(entries)
    report["hash_exclusions"] = excluded
    scan = scan_tracked_public_tree(root)
    report["existing_scanner_text_files"] = scan["scanned_text_files"]
    for rel, issues in scan["findings"].items():
        report["findings"].append(dict(path=rel, surface="existing_tracked_scanner", issues=issues))
    # The reused scanner limits suffixes; inspect every remaining tracked path
    # too. Forbidden paths are rejected without opening potential private data.
    tracked = sorted(names(git(root, "ls-files", "--cached", "-z")))
    read_count = 0
    legacy_assets = []
    for rel in tracked:
        safe_relative(rel)
        if forbidden_path(rel) or {part.lower() for part in PurePosixPath(rel).parts} & {
                "private", "artifacts", "credentials", "tokens", ".private", ".secrets"}:
            report["findings"].append(dict(path=rel, surface="all_tracked", issues=["forbidden_tracked_path"]))
            continue
        work = read_public(root, rel)
        index = git(root, "show", ":" + rel)
        if rel in LEGACY_PROBLEM_ASSETS:
            legacy_assets.append(verify_legacy_problem_asset(root, rel, work, index, scan_text, RAW_ID))
            read_count += 1
            continue
        for surface, blob in (("worktree", work), ("index", index)):
            issues = scan_public_bytes(rel, blob)
            if issues:
                report["findings"].append(dict(path=rel, surface=surface, issues=issues))
        read_count += 1
    report.update(tracked_paths_enumerated=len(tracked), all_tracked_worktree_files_scanned=read_count,
                  all_tracked_index_blobs_scanned=read_count,
                  legacy_problem_assets_verified=legacy_assets,
                  legacy_problem_statement_illustration_present=bool(legacy_assets),
                  candidate_payload_checked_separately_from_legacy_assets=True,
                  whole_tracked_tree_claimed_free_of_sample_content=False)
    need(not report["findings"], "Public safety findings present")
    protected = ["E题数据/probe.dat", "configs/paths.local.json", ".env", ".env.local",
                 "probe.pkl", "probe.mp4", "probe.pt", "probe.pth", "probe.ckpt",
                 "__pycache__/probe.pyc", "reports/runs/probe/private/probe.json",
                 "reports/runs/probe/artifacts/probe.json"]
    # check-ignore evaluates synthetic names; it does not open their files.
    ignored = names(git(root, "check-ignore", "--no-index", "-z", "--stdin",
                        input_bytes=("\0".join(protected) + "\0").encode("utf-8")))
    need(ignored == set(protected), "Required .gitignore protections missing")
    report["ignore_protection_probes_passed"] = len(protected)
    need(not git(root, "diff", "--name-only", BASELINE, "--", *FROZEN).strip(),
         "Frozen research/data implementation changed")
    need(not any(rel == d or rel.startswith(d + "/") for rel in untracked for d in FROZEN),
         "New untracked file inside frozen paths")
    rows = lambda text: [line for line in text.splitlines() if line.startswith("| D-DATA-")]
    need(rows(git(root, "show", BASELINE + ":DECISIONS.md").decode("utf-8")) ==
         rows(read_public(root, "DECISIONS.md").decode("utf-8")), "D-DATA decision rows changed")
    report.update(frozen_baseline=BASELINE, frozen_paths_unchanged=True, data_contract_unchanged=True)
    check_config(root, mode, report)
    report.update(status="PASS", exit_code=0)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--mode", required=True, choices=("activation", "results"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    root = Path(git(Path.cwd(), "rev-parse", "--show-toplevel").decode().strip()).resolve()
    output = args.output.absolute()
    no_redirect(output)
    need(not output.resolve().is_relative_to(root) and not output.exists(),
         "Output must be a new file outside the repository")
    report = dict(stage="S01_CAMPAIGN_PUBLICATION_CHECK", mode=args.mode, status="FAIL", exit_code=1,
                  checked_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), findings=[],
                  git_mutations=False, release_created=False, competition_data_read=False,
                  native_authorization_journals_read=False, campaign_claimed=False,
                  model_training_performed=False, model_metrics_verified=False,
                  limitations=["Pattern/path checking is not a universal secrecy proof.",
                               "This safety check does not independently validate predictive metrics.",
                               "No tests, official data, native journals, or GPU workloads are executed."])
    try:
        check(root, args.manifest.absolute(), args.mode, report)
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError, ImportError) as exc:
        text = str(exc).replace(str(root), "<REPOSITORY>").replace(root.as_posix(), "<REPOSITORY>")
        text = re.sub(r"[A-Za-z]:[\\/][^\r\n]*", "<REDACTED_PATH>", text)
        report["failure"] = dict(type=type(exc).__name__, message=text)
    report["command"] = "python -B -X utf8 tools/s01_campaign_publication_check.py --manifest " + \
        args.manifest.name + " --mode " + args.mode + " --output NEW_EXTERNAL_REPORT_JSON"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write("\n")
    print(json.dumps(dict(status=report["status"], exit_code=report["exit_code"], mode=args.mode,
                          finding_count=len(report["findings"])), ensure_ascii=False))
    return report["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
