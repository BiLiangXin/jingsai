"""Private Q1 source audit and fixed controlled diagnostics from cached free ASR."""
import argparse
import csv
import hashlib
import json
import math
import time
from collections import Counter
from pathlib import Path

import numpy as np
import av

from mosei.autoqc.core import audit_window, unique_exact_matches, valid_interval, words


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")


def asr_words(segments, offset):
    tokens, times = [], []
    for segment in segments:
        for token in words(segment["word"]):
            tokens.append(token)
            times.append((offset + float(segment["start"]), offset + float(segment["end"]))
                         if segment["start"] is not None and segment["end"] is not None else None)
    return tokens, times


def evaluate(original, ref, aligned_ref, hyp, a_times, b_times, lower, upper, pts):
    target = list(range(len(ref)))
    result = audit_window(ref, hyp, a_times, b_times, target, lower, upper)
    ordered = [a_times.get(j) for j in range(len(ref))]
    time_ok = all(valid_interval(pair, lower, upper) for pair in ordered)
    if time_ok:
        time_ok = all(right[0] >= left[1] for left, right in zip(ordered, ordered[1:]))
    result["qc0_mechanical"] = bool(original and ref == aligned_ref and time_ok)
    result["qc1_asr_lexical"] = bool(result["qc0_mechanical"] and result["unique_word_fraction"] == 1
                                     and result["transcript_disagreement"] is not None
                                     and result["transcript_disagreement"] <= .35)
    nearest = None
    if result["qc1_asr_lexical"] and b_times and pts.size:
        pairs = unique_exact_matches(ref, hyp)["unique"]
        gaps = [float(np.min(np.abs(pts - (a + b) / 2)))
                for i in target if i in pairs for pair in [b_times[pairs[i]]]
                if pair is not None for a, b in [pair]]
        nearest = max(gaps) if gaps else None
    result["max_nearest_pts_gap"] = nearest
    result["qc2_time_pts_abstention"] = (result["qc1_asr_lexical"]
                                         and result["acoustic_basis"] == "DUAL_CONSISTENT_ESTIMATE"
                                         and nearest is not None and nearest <= .10)
    return result


def main():
    p = argparse.ArgumentParser()
    for arg in ("q1-root", "alignment-root", "source-root", "asr-root", "output"):
        p.add_argument("--" + arg, required=True)
    a = p.parse_args()
    q1, alignment_root, source, asr, out = map(Path, (a.q1_root, a.alignment_root, a.source_root, a.asr_root, a.output))
    out.mkdir(parents=True, exist_ok=False)
    trace = list(csv.DictReader((alignment_root / "TRACE_100.csv").open(encoding="utf-8", newline="")))
    if len(trace) != 100:
        raise ValueError("Q1_TRACE_NOT_100")
    records = []
    start = time.monotonic()
    for i, row in enumerate(trace):
        folder = q1 / f"{i:03d}"
        official = json.loads((folder / "official_row.json").read_text(encoding="utf-8"))
        alignment = json.loads((alignment_root / f"{i:03d}.json").read_text(encoding="utf-8"))
        asr_file = asr / f"{i:03d}.json"
        asr_result = json.loads(asr_file.read_text(encoding="utf-8")) if asr_file.is_file() else None
        source_file = source / row["video_relative"]
        if not source_file.is_file():
            candidates = list(source.glob("*/" + row["video_relative"]))
            if len(candidates) == 1:
                source_file = candidates[0]
        h = {"features_hash_ok": sha(folder / "features.npz") == row["features_sha256"],
             "source_hash_ok": source_file.is_file() and sha(source_file) == row["video_sha256"],
             "audio_pts_contiguous": alignment["audio_contiguous"]}
        feature = np.load(folder / "features.npz")
        pts = np.asarray(feature["video_pts"], dtype=float)
        h["video_pts_monotonic"] = bool(pts.size and np.all(np.isfinite(pts)) and np.all(np.diff(pts) > 0))
        if source_file.is_file() and h["video_pts_monotonic"]:
            with av.open(str(source_file)) as container:
                stream = container.streams.video[0]
                decoded_pts = np.asarray([float(frame.pts * stream.time_base) for frame in container.decode(stream)
                                          if frame.pts is not None], dtype=float)
            h["actual_frame_decode_binding"] = bool(decoded_pts.size and np.all(np.diff(decoded_pts) > 0)
                                                    and max(float(np.min(abs(decoded_pts - x))) for x in pts) <= .01)
        else:
            h["actual_frame_decode_binding"] = False
        h["all"] = all(h.values())
        h["asr_audio_hash_ok"] = asr_result is not None and sha(folder / "audio.wav") == asr_result["audio_sha256"]
        ref = words(str(official["text"]))
        acoustic = {int(x["token_index"]): (float(x["start"]), float(x["end"]))
                    for x in alignment["words"]}
        if asr_result and asr_result["status"] == "COMPLETE" and h["asr_audio_hash_ok"]:
            hyp, b_times = asr_words(asr_result["word_segments"], alignment["audio_start"])
        else:
            hyp, b_times = [], None
        aligned_ref = words(' '.join(x["word"] for x in alignment["words"]))
        result = evaluate(alignment["status"] == "COMPUTED_TEMPORAL_CHECKS_PASS" and h["all"],
                          ref, aligned_ref, hyp, acoustic, b_times, alignment["audio_start"], alignment["audio_end"], pts)
        result.update({"ordinal": i, "source_sha256": row["video_sha256"], "source_h": h,
                       "q1_original_alignment_status": alignment["status"],
                       "asr_status": asr_result["status"] if asr_result else "NOT_EVALUATED",
                       "reference_word_count": len(ref), "free_asr_word_count": len(hyp),
                       "group": "development" if int(hashlib.sha256(str(official["video_id"]).encode()).hexdigest(), 16) % 2 == 0 else "holdout"})
        records.append(result)
    save(out / "Q1_SOURCE_AUDIT_PRIVATE.json", records)
    counts = {key: sum(bool(x[key]) for x in records)
              for key in ("qc0_mechanical", "qc1_asr_lexical", "qc2_time_pts_abstention")}
    counts["acoustic_basis"] = dict(Counter(x["acoustic_basis"] for x in records))
    counts["h_all"] = sum(x["source_h"]["all"] for x in records)
    counts["group"] = dict(Counter(x["group"] for x in records))
    counts["asr_complete"] = sum(x["asr_status"] == "COMPLETE" for x in records)
    counts["source_rows"] = len(records)
    counts["elapsed_seconds"] = time.monotonic() - start
    counts["natural_alignment_accuracy"] = None
    save(out / "Q1_AGGREGATE.json", counts)
    # Diagnostics operate on copies. Fault type is held by this evaluator, never passed to core.audit_window.
    selected = sorted(range(100), key=lambda i: hashlib.sha256((trace[i]["video_sha256"] + ':17').encode()).digest())[:12]
    diagnostics = []
    for i in selected:
        folder = q1 / f"{i:03d}"
        official = json.loads((folder / "official_row.json").read_text(encoding="utf-8"))
        alignment = json.loads((alignment_root / f"{i:03d}.json").read_text(encoding="utf-8"))
        result = json.loads((asr / f"{i:03d}.json").read_text(encoding="utf-8")) if (asr / f"{i:03d}.json").is_file() else None
        if not result or result["status"] != "COMPLETE":
            continue
        ref = words(str(official["text"]))
        aligned_ref = words(' '.join(x["word"] for x in alignment["words"]))
        hyp, b = asr_words(result["word_segments"], alignment["audio_start"])
        at = {int(x["token_index"]): (float(x["start"]), float(x["end"])) for x in alignment["words"]}
        lo, hi = alignment["audio_start"], alignment["audio_end"]
        feature = np.load(folder / "features.npz")
        pts = np.asarray(feature["video_pts"], dtype=float)
        baseline = alignment["status"] == "COMPUTED_TEMPORAL_CHECKS_PASS"
        cases = [("unchanged_copy", ref[:], dict(at), hyp[:], b[:], lo, hi, pts.copy())]
        for shift in (.5, 1.):
            changed = {k: (v[0] + shift, v[1] + shift) for k, v in at.items()}
            cases.append((f"sidecar_shift_{shift}", ref[:], changed, hyp[:], b[:], lo, hi, pts.copy()))
        if len(ref) >= 2:
            swapped = ref[:]
            swapped[0], swapped[1] = swapped[1], swapped[0]
            cases.append(("adjacent_word_swap", swapped, dict(at), hyp[:], b[:], lo, hi, pts.copy()))
        if any(t in ("not", "no", "don't") for t in ref):
            changed = ["yes" if t in ("not", "no", "don't") else t for t in ref]
            cases.append(("negation_change", changed, dict(at), hyp[:], b[:], lo, hi, pts.copy()))
        for kind, rr, aa, hh, bb, low, high, vv in cases:
            scored = evaluate(baseline, rr, aligned_ref, hh, aa, bb, low, high, vv)
            diagnostics.append({"ordinal": i, "fault_type": kind,
                                "qc0": scored["qc0_mechanical"],
                                "qc1": scored["qc1_asr_lexical"],
                                "qc2": scored["qc2_time_pts_abstention"],
                                "reason_codes": scored["reason_codes"]})
    save(out / "CONTROLLED_PERTURBATION_PRIVATE.json", diagnostics)
    aggregate = {kind: {"count": sum(x["fault_type"] == kind for x in diagnostics),
                         "qc0_rejected": sum(x["fault_type"] == kind and not x["qc0"] for x in diagnostics),
                         "qc1_rejected": sum(x["fault_type"] == kind and not x["qc1"] for x in diagnostics),
                         "qc2_rejected": sum(x["fault_type"] == kind and not x["qc2"] for x in diagnostics)}
                 for kind in sorted(set(x["fault_type"] for x in diagnostics))}
    aggregate["scope_warning"] = "Controlled perturbation detection, not natural alignment accuracy; prefix silence/audio swap not yet evaluated."
    save(out / "CONTROLLED_PERTURBATION_AGGREGATE.json", aggregate)
    print(json.dumps({"q1_attempted": len(records), "asr_complete": counts["asr_complete"],
                      "qc2": counts["qc2_time_pts_abstention"], "perturbations": len(diagnostics)}))


if __name__ == "__main__":
    main()
