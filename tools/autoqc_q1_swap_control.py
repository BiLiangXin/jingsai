"""Source-binding control: deterministic duration-matched Q1 audio swaps."""
import argparse
import csv
import hashlib
import json
import wave
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def duration(path):
    with wave.open(str(path), "rb") as f:
        return f.getnframes() / f.getframerate()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--q1-root", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    q1, out = Path(a.q1_root), Path(a.output)
    trace = list(csv.DictReader((q1 / "TRACE_100.csv").open(encoding="utf-8")))
    if len(trace) != 100:
        raise ValueError("Q1_COUNT_MISMATCH")
    selected = sorted(range(100), key=lambda i: hashlib.sha256((trace[i]["video_sha256"] + ':17').encode()).digest())[:12]
    out.mkdir(parents=True, exist_ok=False)
    results = []
    for i in selected:
        original = q1 / f"{i:03d}" / "audio.wav"
        original_duration = duration(original)
        donors = sorted((j for j in range(100) if j != i),
                        key=lambda j: hashlib.sha256((trace[j]["video_sha256"] + ':swap:17').encode()).digest())
        donors = [j for j in donors if .8 <= duration(q1 / f"{j:03d}" / "audio.wav") / original_duration <= 1.25]
        if not donors:
            results.append({"ordinal": i, "status": "INELIGIBLE_DURATION"})
            continue
        j = donors[0]
        alternate = q1 / f"{j:03d}" / "audio.wav"
        copy = out / f"{i:03d}.wav"
        copy.write_bytes(alternate.read_bytes())
        result = {"ordinal": i, "donor_ordinal": j,
                  "source_audio_sha256": sha(original), "diagnostic_audio_sha256": sha(copy),
                  "duration_ratio": duration(copy) / original_duration,
                  "source_binding_detected": sha(original) != sha(copy)}
        results.append(result)
    (out / "SWAP_PRIVATE.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    aggregate = {"selected": len(selected), "eligible": sum("source_binding_detected" in r for r in results),
                 "detected_by_source_hash": sum(r.get("source_binding_detected", False) for r in results),
                 "natural_alignment_accuracy": None}
    (out / "SWAP_AGGREGATE.json").write_text(json.dumps(aggregate, indent=2), encoding="utf-8")
    print(json.dumps(aggregate))


if __name__ == "__main__":
    main()
