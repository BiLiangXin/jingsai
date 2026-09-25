"""Portable, single-record S04 feature-space inference entry.

The official population run is tools/s04_io_run.py with its reviewed source gate.
This entry is for reproducing a supplied, trusted aligned record or the synthetic demo.
"""
import argparse
import json
import pickle
from pathlib import Path

import numpy as np

from mosei.s01.contracts import require
from mosei.s04.inference import (
    load_locked_model, model_state_hash, parse_aligned_special,
    predict_and_explain, sha_file,
)

EXPORT_SHA256 = 'e1de989a8b1f6918c164f668451378911ae344ac980630a6fc38ad10f4da107c'


def main():
    parser = argparse.ArgumentParser(description='Frozen M2/V1 single aligned-record inference')
    parser.add_argument('--model', required=True, help='Bundled M2_seed17_inference.pt')
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--input-npz', help='Continuous text/audio/vision and text_bert arrays')
    source.add_argument('--trusted-official-pkl', help='Locally verified official aligned PKL only')
    parser.add_argument('--input-sha256', help='Required for trusted official PKL')
    parser.add_argument('--output', required=True, help='New private JSON output; never overwritten')
    args = parser.parse_args()
    model_path = Path(args.model)
    require(sha_file(model_path) == EXPORT_SHA256, 'Inference export hash changed')
    if args.input_npz:
        require(args.input_sha256 is None, 'Input digest applies only to official PKL')
        with np.load(args.input_npz, allow_pickle=False) as arrays:
            item = {key: arrays[key] for key in arrays.files}
    else:
        path = Path(args.trusted_official_pkl)
        require(path.suffix.lower() == '.pkl' and args.input_sha256 is not None,
                'Trusted official PKL requires explicit SHA256')
        require(sha_file(path) == args.input_sha256.lower(), 'Official input digest mismatch')
        with path.open('rb') as stream:
            item = pickle.load(stream)
    arrays, support, identifier = parse_aligned_special(item)
    model, normalizer = load_locked_model(model_path, inference_export=True, device='cpu')
    before = model_state_hash(model)
    answer = predict_and_explain(model, normalizer, arrays, support, device='cpu')
    require(model_state_hash(model) == before, 'Model state changed')
    output = Path(args.output)
    require(not output.exists(), 'Output already exists')
    output.parent.mkdir(parents=True, exist_ok=True)
    result = dict(status='PARTIAL_FEATURE_SPACE_ONLY', model_export_sha256=EXPORT_SHA256,
                  source_sha256=sha_file(args.input_npz or args.trusted_official_pkl),
                  source_identifier=identifier, prediction=answer,
                  mapping_status='UNVERIFIED_MAPPING', special_metrics=None,
                  model_state_unchanged=True)
    with output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write('\n')
    print(json.dumps(dict(status=result['status'], output=str(output))))


if __name__ == '__main__':
    main()
