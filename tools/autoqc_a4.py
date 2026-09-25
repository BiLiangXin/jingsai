"""Private Attachment-4 audio preparation and immutable-prediction evidence sidecar."""
import argparse
import csv
import hashlib
import json
import math
import re
import subprocess
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit, unquote
from urllib.request import url2pathname

import av

from mosei.autoqc.core import audit_window, words

FROZEN_MAPPED_CSV_SHA256 = "ae3698d3df544cf0ec3b0f82f2bdd6d669be86582cfe7a4c862aa17b7b572f7f"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def save(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")


def video_path(card):
    url = urlsplit(card["video_uri"])
    if url.scheme != "file":
        raise ValueError("VIDEO_URI_NOT_LOCAL")
    return Path(url2pathname(unquote(url.path)))


def prepare(cards_path, prior_dir, output, ffmpeg):
    cards = json.loads(Path(cards_path).read_text(encoding="utf-8"))["cards"]
    if len(cards) != 20:
        raise ValueError("A4_CARDS_NOT_20")
    output.mkdir(parents=True, exist_ok=False)
    entries = []
    for i, card in enumerate(cards):
        prior = json.loads((Path(prior_dir) / f"row_{i:02d}.json").read_text(encoding="utf-8"))
        video = video_path(card)
        if sha(video) != card["source_video_sha256"] or sha(video) != prior["video_sha256"]:
            raise ValueError("VIDEO_SOURCE_HASH_MISMATCH")
        if sha(card["source_file"]) != prior["source_sha256"]:
            raise ValueError("FEATURE_SOURCE_HASH_MISMATCH")
        folder = output / f"{i:03d}"
        folder.mkdir()
        wav = folder / "audio.wav"
        process = subprocess.run([str(ffmpeg), "-nostdin", "-hide_banner", "-loglevel", "info", "-copyts",
                                  "-i", str(video), "-map", "0:a:0", "-vn", "-af", "aresample=16000,ashowinfo",
                                  "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", "-f", "wav", str(wav)],
                                 capture_output=True, timeout=120)
        if process.returncode != 0 or not wav.is_file():
            raise RuntimeError("AUDIO_DECODE_FAILED")
        events = [float(s) for s in re.findall(rb"pts_time:([-+\d.eE]+)", process.stderr)]
        if not events or abs(events[0] - float(prior["audio_start_pts"])) > .002:
            raise ValueError("AUDIO_PTS_OFFSET_MISMATCH")
        entries.append({"ordinal": i, "video_sha256": prior["video_sha256"],
                        "feature_sha256": prior["source_sha256"],
                        "audio_sha256": sha(wav), "audio_start_pts": events[0],
                        "old_audio_start_pts": prior["audio_start_pts"]})
    save(output / "AUDIO_SOURCE_BINDING.json", entries)
    print(json.dumps({"prepared": len(entries), "source_binding": "PASS"}))


def decode_pts(video):
    with av.open(str(video)) as container:
        stream = container.streams.video[0]
        pts = []
        for frame in container.decode(stream):
            if frame.pts is None:
                continue
            pts.append(float(frame.pts * stream.time_base))
        if not pts or any(not math.isfinite(x) for x in pts) or any(b <= a for a, b in zip(pts, pts[1:])):
            raise ValueError("VIDEO_PTS_INVALID")
        return pts


def check_unchanged_card(card, source_row):
    if str(card["sample_id"]) != str(source_row["sample_id"]):
        raise ValueError("A4_ORDER_MISMATCH")
    if str(card["polarity"]) != str(source_row["polarity"]) or float(card["intensity"]) != float(source_row["intensity"]):
        raise ValueError("A4_PREDICTION_CHANGED")
    if (card["class_main_modality"] != source_row["class_main_modality"]
            or card["reg_main_modality"] != source_row["reg_main_modality"]):
        raise ValueError("A4_MAIN_MODALITY_CHANGED")
    for target in ("class", "reg"):
        if any(float(card[target + "_phi"][m]) != float(source_row[target + "_phi_" + m]) for m in ("T", "A", "V")):
            raise ValueError("A4_CONTRIBUTION_CHANGED")
        original_windows = json.loads(source_row[target + "_windows_json"])
        card_windows = [w["original"] for w in card["windows"] if w["target"] == target]
        if original_windows != card_windows:
            raise ValueError("A4_KEY_WINDOWS_CHANGED")


def unmapped_ordinary_or_unknown(unmapped):
    return any(u.get("reason", "UNKNOWN") not in
               {"PUNCTUATION_NO_WORD_SPAN", "SPECIAL_TOKEN_NO_DIRECT_WORD_SPAN", "PADDING"}
               for u in unmapped)


def audit(cards_path, prior_dir, audio_dir, asr_dir, frozen_csv, output):
    cards = json.loads(Path(cards_path).read_text(encoding="utf-8"))["cards"]
    source_rows = list(csv.DictReader(Path(frozen_csv).open(encoding="utf-8", newline="")))
    if sha(frozen_csv) != FROZEN_MAPPED_CSV_SHA256:
        raise ValueError("A4_FROZEN_CSV_HASH_MISMATCH")
    audio_binding = json.loads((Path(audio_dir) / "AUDIO_SOURCE_BINDING.json").read_text(encoding="utf-8"))
    if len(cards) != 20 or len(source_rows) != 20 or len(audio_binding) != 20:
        raise ValueError("A4_COUNT_MISMATCH")
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    for i, (card, source_row, binding) in enumerate(zip(cards, source_rows, audio_binding)):
        prior = json.loads((Path(prior_dir) / f"row_{i:02d}.json").read_text(encoding="utf-8"))
        asr = json.loads((Path(asr_dir) / f"{i:03d}.json").read_text(encoding="utf-8"))
        video = video_path(card)
        check_unchanged_card(card, source_row)
        h = {"video_hash_ok": sha(video) == prior["video_sha256"] == binding["video_sha256"],
             "feature_hash_ok": sha(card["source_file"]) == prior["source_sha256"] == binding["feature_sha256"],
             "audio_hash_ok": sha(Path(audio_dir) / f"{i:03d}" / "audio.wav") == binding["audio_sha256"] == asr["audio_sha256"],
             "audio_offset_ok": abs(binding["audio_start_pts"] - prior["audio_start_pts"]) <= .002}
        if not all(h.values()):
            raise ValueError("A4_SOURCE_BINDING_FAILED")
        actual_pts = decode_pts(video)
        ref = words(card["original_text"])
        if prior["words"] and [x["text"] for x in prior["words"]] != ref:
            raise ValueError("A4_OFFICIAL_WORD_MAPPING_CHANGED")
        hyp, b_times = [], []
        if asr["status"] == "COMPLETE":
            for segment in asr["word_segments"]:
                for token in words(segment["word"]):
                    hyp.append(token)
                    if segment["start"] is None or segment["end"] is None:
                        b_times.append(None)
                    else:
                        b_times.append((prior["audio_start_pts"] + float(segment["start"]),
                                        prior["audio_start_pts"] + float(segment["end"])))
        else:
            b_times = None
        a_times = {j: (float(w["start"]), float(w["end"])) for j, w in enumerate(prior["words"])}
        audited = []
        for window in card["windows"]:
            target = [int(s["word_index"]) for s in window["mapped_text_spans"]]
            outcome = audit_window(ref, hyp, a_times, b_times, target,
                                   prior["audio_start_pts"], prior["audio_end_pts"])
            unmapped_reasons = [u.get("reason", "UNKNOWN") for u in window["unmapped"]]
            if unmapped_ordinary_or_unknown(window["unmapped"]):
                outcome["acoustic_basis"] = "TEXT_ONLY"
                outcome["reason_codes"].append("UNMAPPED_ORDINARY_OR_UNKNOWN_TOKEN")
            gaps = []
            for j in outcome.get("matched_ref_indices", []):
                match = outcome.get("acoustic_basis")
                if match in ("DUAL_CONSISTENT_ESTIMATE", "SINGLE_ASR_ESTIMATE"):
                    # Only frame existence is certified; exact feature production time is unknown.
                    from mosei.autoqc.core import unique_exact_matches
                    k = unique_exact_matches(ref, hyp)["unique"].get(j)
                    if k is not None and b_times and b_times[k] is not None:
                        mid = sum(b_times[k]) / 2
                        gaps.append(min(abs(t - mid) for t in actual_pts))
            frame = "NEAR_FRAME" if gaps and max(gaps) <= .10 else "NO_NEAR_FRAME" if gaps else "NO_ACOUSTIC_FRAME_REFERENCE"
            audited.append({"target": window["target"], "rank": window["rank"],
                            "main_modality": window["main_modality"],
                            "original_window_sha256": hashlib.sha256(json.dumps(window, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
                            "ordinary_target_word_count": len(set(target)),
                            "unmapped_token_count": len(window["unmapped"]),
                            "unmapped_reason_counts": dict(Counter(unmapped_reasons)),
                            "text_basis": "TEXT_SPAN" if target else "NO_DIRECT_WORD_SPAN",
                            "reference_frame_status": frame,
                            "official_av_feature_production_timing": "UNKNOWN", **outcome})
        rows.append({"ordinal": i, "original_prediction_row_sha256": hashlib.sha256(json.dumps(source_row, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
                     "source_h": h, "asr_status": asr["status"], "window_count": len(audited),
                     "model_prediction_status": "UNCHANGED", "windows": audited})
    save(output / "A4_SOURCE_AUDIT_PRIVATE.json", rows)
    statuses = Counter(w["acoustic_basis"] for r in rows for w in r["windows"])
    record_status = Counter("DUAL_CONSISTENT_ESTIMATE" if r["windows"] and all(w["acoustic_basis"] == "DUAL_CONSISTENT_ESTIMATE" for w in r["windows"])
                            else "EVIDENCE_GAP_OR_CONFLICT" for r in rows)
    aggregate = {"rows": len(rows), "windows": sum(r["window_count"] for r in rows),
                 "window_acoustic_basis": dict(statuses), "record_basis": dict(record_status),
                 "original_csv_sha256": sha(frozen_csv), "original_predictions_unchanged": True,
                 "official_av_feature_production_timing": "UNKNOWN",
                 "natural_alignment_accuracy": None, "new_human_reviews": 0}
    save(output / "A4_AGGREGATE.json", aggregate)
    print(json.dumps(aggregate))


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="mode", required=True)
    prep = sub.add_parser("prepare")
    for key in ("cards", "prior-dir", "output", "ffmpeg"):
        prep.add_argument("--" + key, required=True)
    run = sub.add_parser("audit")
    for key in ("cards", "prior-dir", "audio-dir", "asr-dir", "frozen-csv", "output"):
        run.add_argument("--" + key, required=True)
    a = p.parse_args()
    if a.mode == "prepare":
        prepare(a.cards, a.prior_dir, Path(a.output), a.ffmpeg)
    else:
        audit(a.cards, a.prior_dir, a.audio_dir, a.asr_dir, a.frozen_csv, Path(a.output))


if __name__ == "__main__":
    main()
