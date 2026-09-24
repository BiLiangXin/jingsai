"""Verify exact owner approval from SSH trust or the native local user event.

No signing, enrollment, host-journal writes or repository receipt trust. Native
confirmation assumes an uncompromised local Codex host and OS account; it is not
cryptographic authentication. That trust boundary is displayed in the question.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
import ctypes
import os
import stat
from pathlib import Path

OWNER = "BiLiangXin"
NAMESPACE = "mosei-s00e-e19"
# Native task identity observed through the Codex host, not supplied by a receipt.
HOST_THREAD_ID = "01a0cf05-378e-7420-ad1a-e44d9faa57f3"


class ApprovalError(ValueError):
    pass


def approval_question(task_id: str, run_id: str, review_hash: str, manifest_hash: str) -> str:
    return (f"本地批准 S00E 发布审核。task_id: {task_id}; run_id: {run_id}; "
            f"review_sha256: {review_hash}; manifest_sha256: {manifest_hash}。"
            "是否批准上述确切版本？请明确回复“批准”。"
            "本批准信任本机 Codex 宿主会话记录，不等同于密码学签名。")


def _validate_host_events(events: list[dict], question: str) -> dict:
    """Pure parser for a native host journal; synthetic fixtures call this directly."""
    requests, acknowledgements, replies = {}, {}, []
    for index, event in enumerate(events):
        if event.get("type") != "response_item":
            continue
        payload = event.get("payload", {})
        kind = payload.get("type")
        if kind == "function_call" and payload.get("name") == "request_user_input_async":
            arguments = json.loads(payload["arguments"])
            if arguments != {"questions": [{"title": question}]}:
                continue
            call_id = payload.get("call_id")
            if not isinstance(call_id, str) or call_id in requests:
                raise ApprovalError("Ambiguous native approval request")
            requests[call_id] = index
        elif kind == "function_call_output" and payload.get("call_id") in requests:
            call_id = payload["call_id"]
            if call_id in acknowledgements or json.loads(payload["output"]).get("accepted") is not True:
                raise ApprovalError("Native approval request was not accepted")
            acknowledgements[call_id] = index
        elif kind == "message" and payload.get("role") == "user":
            for block in payload.get("content", []):
                if block.get("type") != "input_text":
                    continue
                text = block.get("text", "")
                start, end = "<send_user_message_question_reply>", "</send_user_message_question_reply>"
                if not text.startswith(start) or not text.rstrip().endswith(end):
                    continue
                answer_items = json.loads(text[len(start):text.rfind(end)].strip())
                if not isinstance(answer_items, list):
                    raise ApprovalError("Malformed native approval reply")
                for item in answer_items:
                    if item.get("question") != question:
                        continue
                    item_id = json.loads(item["questionItemId"])
                    if (not isinstance(item_id, list) or len(item_id) != 3 or
                            item_id[0] != "request_user_input_async" or type(item_id[2]) is not int or item_id[2] != 0):
                        raise ApprovalError("Native approval reply identity mismatch")
                    call_id = item_id[1]
                    if (call_id not in requests or call_id not in acknowledgements or
                            not requests[call_id] < acknowledgements[call_id] < index or
                            item.get("answer") != "批准"):
                        raise ApprovalError("Native approval is absent, declined or unlinked")
                    if not isinstance(event.get("timestamp"), str) or not event["timestamp"]:
                        raise ApprovalError("Native approval timestamp missing")
                    replies.append({"source": "CODEX_NATIVE_USER_EVENT", "thread_id": HOST_THREAD_ID,
                                    "call_id": call_id, "timestamp": event.get("timestamp"),
                                    "event_sha256": hashlib.sha256(json.dumps(event, sort_keys=True,
                                      ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()})
    if len(replies) != 1 or len(requests) != 1:
        raise ApprovalError("MANUAL_REVIEW_APPROVAL_REQUIRED: one unambiguous native user approval required")
    return replies[0]


def validate_host_events(events: list[dict], question: str) -> dict:
    try:
        return _validate_host_events(events, question)
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        if isinstance(exc, ApprovalError):
            raise
        raise ApprovalError("Malformed native approval event") from exc


def native_sessions_root() -> Path:
    """Use the Windows profile API; environment/path arguments cannot move trust."""
    if os.name != "nt":
        raise ApprovalError("Native approval host unavailable on this platform")
    profile = ctypes.create_unicode_buffer(32768)
    if ctypes.windll.shell32.SHGetFolderPathW(None, 0x28, None, 0, profile) != 0:
        raise ApprovalError("Native approval host profile unavailable")
    return Path(profile.value) / ".codex" / "sessions"


def reject_redirected_path(path: Path) -> None:
    # Inspect original components before resolve can erase a junction boundary.
    for part in (path, *path.parents):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise ApprovalError("Redirected native approval path rejected")


def _verify_native_host(payload: bytes) -> dict:
    """Re-read host-owned events. No repository copy or editable receipt is read.

    Trust assumes the local Codex host/OS account is uncompromised. This is the
    user-authorized local confirmation path, not cryptographic authentication.
    """
    value = json.loads(payload)
    question = approval_question(value["task_id"], value["run_id"],
                                 value["review_sha256"], value["manifest_sha256"])
    root = native_sessions_root()
    reject_redirected_path(root)
    if root.is_symlink() or not root.is_dir():
        raise ApprovalError("Native approval journal unavailable")
    events = []
    for path in sorted(root.rglob(f"*{HOST_THREAD_ID}*.jsonl")):
        reject_redirected_path(path)
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ApprovalError("Unsafe native approval journal")
        with path.open(encoding="utf-8") as stream:
            rows = [json.loads(line) for line in stream if line.strip()]
        if (not rows or rows[0].get("type") != "session_meta" or
                rows[0].get("payload", {}).get("id") != HOST_THREAD_ID or
                rows[0]["payload"].get("originator") != "Codex Desktop"):
            raise ApprovalError("Native approval session identity mismatch")
        events.extend(rows)
    return validate_host_events(events, question)


def verify_native_host(payload: bytes) -> dict:
    try:
        return _verify_native_host(payload)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        if isinstance(exc, ApprovalError):
            raise
        raise ApprovalError("Native approval source unavailable or malformed") from exc


def approval_payload(root: Path, review_path: Path, task_id: str, run_id: str) -> bytes:
    manifest = root / "reports" / "runs" / run_id / "public/HANDOFF_INPUTS.json"
    value = {"purpose": NAMESPACE, "repository": "BiLiangXin/jingsai",
             "branch": "codex/mosei-auto", "task_id": task_id, "stage": "S00E",
             "run_id": run_id, "review_sha256": hashlib.sha256(review_path.read_bytes()).hexdigest(),
             "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest()}
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def owner_signing_keys() -> list[str]:
    """Fetch the fixed owner's signing keys, not an agent-controlled local list."""
    result = subprocess.run(["gh", "api", "--hostname", "github.com", f"users/{OWNER}/ssh_signing_keys", "--paginate"],
                            capture_output=True, timeout=30)
    if result.returncode:
        raise ApprovalError("MANUAL_REVIEW_APPROVAL_REQUIRED: owner signing keys unavailable")
    try:
        rows = json.loads(result.stdout)
        keys = [row["key"] for row in rows]
        if (not keys or not all(isinstance(key, str) and re.fullmatch(
                r"(?:ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp256) [A-Za-z0-9+/=]+", key) for key in keys)):
            raise ValueError("No valid owner signing key")
    except (ValueError, KeyError, TypeError) as exc:
        raise ApprovalError("MANUAL_REVIEW_APPROVAL_REQUIRED: enroll an owner-controlled signing key") from exc
    return keys


def verify_owner_signature(payload: bytes, signature: Path) -> None:
    if signature.is_symlink() or not signature.is_file() or signature.stat().st_size > 16384:
        raise ApprovalError("MANUAL_REVIEW_APPROVAL_REQUIRED: owner signature missing or unsafe")
    keys = owner_signing_keys()
    with tempfile.TemporaryDirectory(prefix="mosei-approval-") as temp:
        allowed = Path(temp) / "allowed_signers"
        allowed.write_text("".join(f"{OWNER} {key}\n" for key in keys), encoding="utf-8")
        result = subprocess.run(["ssh-keygen", "-Y", "verify", "-f", str(allowed),
                                 "-I", OWNER, "-n", NAMESPACE, "-s", str(signature)],
                                input=payload, capture_output=True, timeout=30)
    if result.returncode:
        raise ApprovalError("MANUAL_REVIEW_APPROVAL_REQUIRED: owner signature invalid for current review")


def verify(root: Path, review_path: Path, task_id: str, run_id: str) -> None:
    signature = root / "reports" / "runs" / run_id / "private/OWNER_APPROVAL.sig"
    payload = approval_payload(root, review_path, task_id, run_id)
    if signature.exists():
        verify_owner_signature(payload, signature)
        return
    verify_native_host(payload)
