"""Fixed Q1 audio-only controls; private records and no official transcript prompt."""
import argparse
import csv
import datetime as dt
import hashlib
import json
import time
import wave
from pathlib import Path

from mosei.autoqc.core import unique_exact_matches, words


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser()
    for key in ("q1-root", "asr-root", "model-dir", "protocol", "output", "deadline-utc"):
        p.add_argument("--" + key, required=True)
    a = p.parse_args()
    q1, asr, model_dir, out = map(Path, (a.q1_root, a.asr_root, a.model_dir, a.output))
    spec = json.loads(Path(a.protocol).read_text(encoding="utf-8"))["asr"]
    for file, key in (("model.bin", "model_bin_sha256"), ("tokenizer.json", "tokenizer_sha256"),
                      ("config.json", "config_sha256"), ("vocabulary.txt", "vocabulary_sha256")):
        if digest(model_dir / file) != spec[key]:
            raise ValueError("MODEL_HASH_MISMATCH")
    trace = list(csv.DictReader((q1 / "TRACE_100.csv").open(encoding="utf-8")))
    selected = sorted(range(100), key=lambda i: hashlib.sha256((trace[i]["video_sha256"] + ':17').encode()).digest())[:12]
    out.mkdir(parents=True, exist_ok=False)
    from faster_whisper import WhisperModel
    model = WhisperModel(str(model_dir), device=spec["device"], compute_type=spec["compute_type"])
    deadline = dt.datetime.fromisoformat(a.deadline_utc.replace("Z", "+00:00"))
    records = []
    for i in selected:
        if dt.datetime.now(dt.timezone.utc) >= deadline:
            break
        source = q1 / f"{i:03d}" / "audio.wav"
        with wave.open(str(source), "rb") as reader:
            if reader.getnchannels() != 1 or reader.getsampwidth() != 2 or reader.getframerate() != 16000:
                raise ValueError("WAV_FORMAT_CHANGED")
            payload = reader.readframes(reader.getnframes())
        folder = out / f"{i:03d}"
        folder.mkdir()
        shifted = folder / "prefix_silence.wav"
        with wave.open(str(shifted), "wb") as writer:
            writer.setnchannels(1)
            writer.setsampwidth(2)
            writer.setframerate(16000)
            writer.writeframes(b"\x00" * 32000 + payload)
        start = time.monotonic()
        segments, _ = model.transcribe(str(shifted), language=spec["language"], task=spec["task"],
                                       temperature=spec["temperature"], beam_size=spec["beam_size"],
                                       word_timestamps=spec["word_timestamps"],
                                       condition_on_previous_text=spec["condition_on_previous_text"],
                                       initial_prompt=spec["initial_prompt"], hotwords=spec["hotwords"],
                                       vad_filter=spec["vad_filter"])
        shifted_words = [{"word": w.word, "start": w.start, "end": w.end}
                         for segment in segments for w in (segment.words or [])]
        (folder / "PREFIX_ASR_PRIVATE.json").write_text(json.dumps(shifted_words, ensure_ascii=False), encoding="utf-8")
        original = json.loads((asr / f"{i:03d}.json").read_text(encoding="utf-8"))["word_segments"]
        baseline_tokens, baseline_times = [], []
        changed_tokens, changed_times = [], []
        for segment, tokens, times in ((original, baseline_tokens, baseline_times),
                                       (shifted_words, changed_tokens, changed_times)):
            for part in segment:
                for token in words(part["word"]):
                    tokens.append(token)
                    times.append((part["start"], part["end"]))
        matching = unique_exact_matches(baseline_tokens, changed_tokens)
        errors = []
        for old, new in matching["unique"].items():
            a_pair, b_pair = baseline_times[old], changed_times[new]
            if None not in a_pair and None not in b_pair:
                errors.append(max(abs((b_pair[0] - a_pair[0]) - 1), abs((b_pair[1] - a_pair[1]) - 1)))
        records.append({"ordinal": i, "source_audio_sha256": digest(source),
                        "prefix_audio_sha256": digest(shifted), "unique_matches": len(errors),
                        "max_shift_equivariance_error_seconds": max(errors) if errors else None,
                        "elapsed_seconds": time.monotonic() - start,
                        "natural_time_truth": None})
        print(json.dumps({"processed": len(records), "unique_matches": len(errors)}), flush=True)
    (out / "PREFIX_CONTROL_RESULTS_PRIVATE.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    summary = {"attempted": len(records), "selected": len(selected),
               "with_unique_matches": sum(bool(r["unique_matches"]) for r in records),
               "max_error_seconds": max((r["max_shift_equivariance_error_seconds"] for r in records
                                         if r["max_shift_equivariance_error_seconds"] is not None), default=None),
               "natural_alignment_accuracy": None}
    (out / "PREFIX_CONTROL_AGGREGATE.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
