"""Run the frozen general ASR on audio alone; output stays private.

No official text, alignment, labels or sentiment model is read by this process.
"""
import argparse
import datetime as dt
import hashlib
import json
import platform
import time
from pathlib import Path


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--audio-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--deadline-utc", required=True)
    parser.add_argument("--expected-count", type=int, choices=(20, 100), default=100)
    args = parser.parse_args()
    protocol = json.loads(Path(args.protocol).read_text(encoding="utf-8"))
    spec = protocol["asr"]
    model_dir = Path(args.model_dir)
    for name, key in (("model.bin", "model_bin_sha256"),
                      ("tokenizer.json", "tokenizer_sha256"),
                      ("config.json", "config_sha256"),
                      ("vocabulary.txt", "vocabulary_sha256")):
        if digest(model_dir / name) != spec[key]:
            raise ValueError("MODEL_HASH_MISMATCH:" + name)
    import faster_whisper
    if faster_whisper.__version__ != spec["package_version"]:
        raise ValueError("PACKAGE_VERSION_MISMATCH")
    from faster_whisper import WhisperModel
    files = sorted(Path(args.audio_root).glob("[0-9][0-9][0-9]/audio.wav"))
    if len(files) != args.expected_count:
        raise ValueError("AUDIO_FILE_COUNT_MISMATCH")
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    deadline = dt.datetime.fromisoformat(args.deadline_utc.replace("Z", "+00:00"))
    model = WhisperModel(str(model_dir), device=spec["device"], compute_type=spec["compute_type"])
    receipt = {"backend": "faster-whisper", "version": faster_whisper.__version__,
               "revision": spec["revision"], "model_bin_sha256": spec["model_bin_sha256"],
               "device": spec["device"], "compute_type": spec["compute_type"],
               "python": platform.python_version(), "cases_attempted": 0, "cases_complete": 0,
               "source_type": "AUDIO_ONLY_NO_OFFICIAL_TEXT_PROMPT", "errors": []}
    for index, file in enumerate(files):
        if dt.datetime.now(dt.timezone.utc) >= deadline:
            receipt["stop_reason"] = "DEADLINE"
            break
        start = time.monotonic()
        result = {"ordinal": index, "audio_sha256": digest(file),
                  "status": "NOT_EVALUATED", "word_segments": []}
        try:
            segments, info = model.transcribe(
                str(file), language=spec["language"], task=spec["task"],
                temperature=spec["temperature"], beam_size=spec["beam_size"],
                word_timestamps=spec["word_timestamps"],
                condition_on_previous_text=spec["condition_on_previous_text"],
                initial_prompt=spec["initial_prompt"], hotwords=spec["hotwords"],
                vad_filter=spec["vad_filter"])
            # Transcription is lazy; exhausting the generator is required.
            result["word_segments"] = [
                {"word": w.word, "start": w.start, "end": w.end}
                for segment in segments for w in (segment.words or [])]
            result["status"] = "COMPLETE"
            result["detected_language"] = info.language
            receipt["cases_complete"] += 1
        except Exception as exc:
            result["error_type"] = type(exc).__name__
            receipt["errors"].append({"ordinal": index, "type": type(exc).__name__})
        result["elapsed_seconds"] = time.monotonic() - start
        (output / f"{index:03d}.json").write_text(json.dumps(result, ensure_ascii=False, allow_nan=False), encoding="utf-8")
        receipt["cases_attempted"] += 1
        print(json.dumps({"attempted": receipt["cases_attempted"],
                          "complete": receipt["cases_complete"],
                          "elapsed_seconds": round(result["elapsed_seconds"], 3)}), flush=True)
    (output / "RECEIPT.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    if receipt["cases_attempted"] == args.expected_count and receipt["cases_complete"] == args.expected_count:
        receipt["status"] = "COMPLETE"
    else:
        receipt["status"] = "PARTIAL"
    (output / "RECEIPT.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
