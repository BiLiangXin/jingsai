"""Private aligned Attachment4 token/acoustic mapping; no predictor or fitting."""
import argparse
import csv
import hashlib
import json
import pickle
import re
import subprocess
from collections import Counter
from pathlib import Path

import numpy as np
import pocketsphinx
from transformers import AutoTokenizer

WORDS = re.compile(r"[a-z]+(?:'[a-z]+)*|[0-9]+")
PTS = re.compile(r"pts_time:([-+\d.eE]+)")
AUDIO_EVENTS = re.compile(r"pts_time:([-+\d.eE]+).*?nb_samples:(\d+)")
FROZEN_OLD_CSV_SHA256 = '6e4cfbb3407d5ccf62ad06aec3907277bf632e65a87ebbc20fa94d707ddb4187'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def decode(ffmpeg, video):
    common = [str(ffmpeg), '-nostdin', '-hide_banner', '-loglevel', 'info', '-copyts', '-i', str(video)]
    audio = subprocess.run(common + ['-map', '0:a:0', '-vn', '-af', 'aresample=16000,ashowinfo', '-ac', '1', '-ar', '16000', '-f', 's16le', 'pipe:1'], capture_output=True, timeout=90)
    if audio.returncode:
        raise ValueError('AUDIO_DECODE_FAILED')
    events = [(float(t), int(n)) for t, n in AUDIO_EVENTS.findall(audio.stderr.decode('utf-8', 'replace'))]
    if not events or len(audio.stdout) % 2:
        raise ValueError('AUDIO_PTS_MISSING')
    if any(abs(t - (previous + n / 16000)) >= .002 for (previous, n), (t, _) in zip(events, events[1:])):
        raise ValueError('AUDIO_PTS_DISCONTINUITY')
    video_run = subprocess.run(common + ['-map', '0:v:0', '-an', '-vf', 'showinfo', '-f', 'null', '-'], capture_output=True, timeout=90)
    if video_run.returncode:
        raise ValueError('VIDEO_DECODE_FAILED')
    vt = np.asarray([float(x) for x in PTS.findall(video_run.stderr.decode('utf-8', 'replace'))], dtype=np.float64)
    if not len(vt) or np.any(np.diff(vt) <= 0):
        raise ValueError('VIDEO_PTS_INVALID')
    start = events[0][0]
    end = start + len(audio.stdout) / 32000
    if end <= start:
        raise ValueError('AUDIO_EMPTY')
    return audio.stdout, start, end, vt


def align(pcm, words, start, end, model):
    decoder = pocketsphinx.Decoder(hmm=str(model / 'en-us/en-us'), dict=str(model / 'en-us/cmudict-en-us.dict'), lm=None, samprate=16000, loglevel='ERROR')
    if any(decoder.lookup_word(w) is None for w in words):
        raise ValueError('DICTIONARY_OOV')
    decoder.set_align_text(' '.join(words))
    decoder.start_utt()
    decoder.process_raw(pcm, full_utt=True)
    decoder.end_utt()
    decoded = decoder.seg()
    if decoded is None:
        raise ValueError('ALIGNER_NO_SEGMENT')
    segments = [s for s in decoded if s.word not in {'<sil>', '<s>', '</s>', '[SPEECH]', '[NOISE]'}]
    canonical = lambda w: re.sub(r'\(\d+\)$', '', w)
    if [canonical(s.word) for s in segments] != words:
        raise ValueError('TOKEN_SEQUENCE_MISMATCH')
    result = []
    for s in segments:
        a = start + s.start_frame / 100
        b = start + (s.end_frame + 1) / 100
        if b <= a or a < start - .011 or b > end + .02 or (result and a < result[-1][1]):
            raise ValueError('WORD_TIME_INVALID')
        result.append((a, b))
    return result


def token_word_indices(offsets, attention, spans):
    result = []
    for (a, b), active in zip(offsets, attention):
        if not active or a == b:
            result.append(None)
            continue
        matches = [i for i, (c, d) in enumerate(spans) if c <= a and b <= d]
        result.append(matches[0] if len(matches) == 1 else None)
    return result


def window_mapping(window, token_to_word, times, video_pts):
    lo, hi = int(window['feature_start']), int(window['feature_end_exclusive'])
    if not (0 <= lo < hi <= len(token_to_word)):
        raise ValueError('WINDOW_BOUNDS')
    ids = sorted(set(i for i in token_to_word[lo:hi] if i is not None))
    if times is None:
        quality = 'TEXT_SPAN_ONLY' if ids else 'UNMAPPABLE'
        return {'quality': quality, 'token_start': lo, 'token_end_exclusive': hi, 'word_indices': ids, 'intervals': [], 'unmapped_token_positions': [i for i in range(lo, hi) if token_to_word[i] is None]}
    intervals = []
    for i in ids:
        a, b = times[i]
        if intervals and a <= intervals[-1]['end'] + 1e-8:
            intervals[-1]['end'] = max(b, intervals[-1]['end'])
            intervals[-1]['word_indices'].append(i)
        else:
            intervals.append({'start': a, 'end': b, 'word_indices': [i]})
    for item in intervals:
        midpoint = (item['start'] + item['end']) / 2
        index = int(np.argmin(abs(video_pts - midpoint)))
        item['nearest_video_pts'] = float(video_pts[index])
    return {'quality': 'ESTIMATED_ACOUSTIC_ALIGNMENT' if intervals else 'UNMAPPABLE', 'token_start': lo, 'token_end_exclusive': hi, 'word_indices': ids, 'intervals': intervals, 'unmapped_token_positions': [i for i in range(lo, hi) if token_to_word[i] is None]}


def main():
    p = argparse.ArgumentParser()
    for name in ['source', 'old-csv', 'tokenizer', 'model', 'ffmpeg', 'output']:
        p.add_argument('--' + name, required=True)
    a = p.parse_args()
    out = Path(a.output)
    out.mkdir(parents=True, exist_ok=False)
    if sha(a.old_csv) != FROZEN_OLD_CSV_SHA256:
        raise ValueError('OLD_CSV_BINDING')
    rows = list(csv.DictReader(Path(a.old_csv).open(newline='', encoding='utf-8')))
    if len(rows) != 20:
        raise ValueError('FROZEN_20_ROW_POPULATION')
    tokenizer = AutoTokenizer.from_pretrained(a.tokenizer, local_files_only=True, use_fast=True)
    summary = Counter()
    mapped_rows = []
    for ordinal, row in enumerate(rows):
        if int(row['sample_index']) != ordinal or int(row['source_row']) != 0:
            raise ValueError('FROZEN_ROW_ORDER')
        feature = Path(a.source) / row['source_file']
        if feature.is_symlink() or not feature.resolve().is_relative_to(Path(a.source).resolve()) or not feature.is_file():
            raise ValueError('SOURCE_SCOPE')
        video = feature.parent / 'videos' / (feature.stem + '.mp4')
        if not video.is_file():
            raise ValueError('SOURCE_VIDEO_MISSING')
        item = pickle.load(feature.open('rb'))
        raw = str(item['raw_text'])
        stored = np.asarray(item['text_bert'])
        enc = tokenizer(raw, max_length=50, truncation=True, padding='max_length', return_offsets_mapping=True)
        expected = np.asarray([enc['input_ids'], enc['attention_mask'], enc['token_type_ids']])
        if stored.shape != (3, 50) or not np.array_equal(stored, expected):
            raise ValueError('TOKENIZER_REPLAY_MISMATCH')
        lower = raw.lower()
        spans = [m.span() for m in WORDS.finditer(lower)]
        words = [m.group() for m in WORDS.finditer(lower)]
        token_to_word = token_word_indices(enc['offset_mapping'], enc['attention_mask'], spans)
        pcm, start, end, vt = decode(a.ffmpeg, video)
        failure = None
        try:
            times = align(pcm, words, start, end, Path(a.model))
        except (ValueError, RuntimeError, TypeError) as exc:
            times = None
            failure = str(exc)
        cards = {}
        for key in ('class_windows_json', 'reg_windows_json'):
            windows = json.loads(row[key])
            cards[key] = [window_mapping(w, token_to_word, times, vt) for w in windows]
            summary.update(card['quality'] for card in cards[key])
        record_quality = 'ESTIMATED_ACOUSTIC_ALIGNMENT' if times is not None else 'TEXT_SPAN_ONLY'
        summary[record_quality + '_RECORDS'] += 1
        mapped = dict(row)
        mapped['mapping_quality'] = record_quality
        mapped['class_mapped_windows_json'] = json.dumps(cards['class_windows_json'], ensure_ascii=False, separators=(',', ':'), allow_nan=False)
        mapped['reg_mapped_windows_json'] = json.dumps(cards['reg_windows_json'], ensure_ascii=False, separators=(',', ':'), allow_nan=False)
        mapped['human_checked'] = 'false'
        mapped_rows.append(mapped)
        private = {'ordinal': ordinal, 'source_file': row['source_file'], 'source_sha256': sha(feature), 'video_sha256': sha(video), 'old_polarity': row['polarity'], 'old_intensity': row['intensity'], 'quality': record_quality, 'failure': failure, 'token_text_exact': True, 'audio_start_pts': start, 'audio_end_pts': end, 'video_pts_count': len(vt), 'words': [{'text': word, 'start': times[i][0], 'end': times[i][1]} for i, word in enumerate(words)] if times is not None else [], 'class_windows': cards['class_windows_json'], 'reg_windows': cards['reg_windows_json'], 'human_checked': False, 'official_timestamp_truth': False, 'shared_window_TAV': True}
        (out / f'row_{ordinal:02d}.json').write_text(json.dumps(private, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    csv_path = out / 'attachment4_predictions_explanations_MAPPED_PARTIAL.csv'
    with csv_path.open('x', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(mapped_rows[0]))
        writer.writeheader()
        writer.writerows(mapped_rows)
    with csv_path.open(newline='', encoding='utf-8') as stream:
        check = list(csv.DictReader(stream))
    if len(check) != len(rows) or any(any(check[i][k] != rows[i][k] for k in rows[i]) for i in range(len(rows))):
        raise ValueError('OLD_PREDICTIONS_CHANGED')
    result = {'status': 'PARTIAL_PENDING_HUMAN_AND_POSITIONAL_REVIEW', 'source_count': len(rows), 'old_csv_sha256': sha(a.old_csv), 'tokenizer_files_private': True, 'quality_counts': dict(summary), 'human_checked': 0, 'new_training_fits': 0, 'no_official_timestamps_claimed': True}
    result['mapped_csv_sha256'] = sha(csv_path)
    (out / 'SUMMARY.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
