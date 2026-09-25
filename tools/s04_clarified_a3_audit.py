"""Read-only clean encoder replay and special token semantics audit; no inference."""
import argparse
import hashlib
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import torch
from transformers import BertModel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from mosei.s04.inference import load_locked_model, inputs_from_record, model_state_hash


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def token_counts(bert):
    b = np.asarray(bert)
    if b.ndim == 2:
        b = b[None]
    if b.ndim != 3 or b.shape[1:] != (3, 50):
        raise ValueError('TOKEN_SHAPE')
    if not np.isfinite(b).all() or not np.array_equal(b, np.round(b)):
        raise ValueError('TOKEN_NONINTEGER_VALUE')
    ids, mask, segments = b[:, 0], b[:, 1], b[:, 2]
    if not np.isin(mask, [0, 1]).all() or not np.isin(segments, [0, 1]).all():
        raise ValueError('TOKEN_CHANNEL_VALUES')
    if np.any((mask[:, :-1] == 0) & (mask[:, 1:] == 1)) or not np.all(mask[:, 0] == 1):
        raise ValueError('SUPPORT_PREFIX')
    active = mask == 1
    if np.any((ids < 0) | (ids >= 30522)) or np.any(ids[~active] != 0):
        raise ValueError('TOKEN_IDS')
    lengths = active.sum(axis=1)
    if np.any(lengths < 2) or np.any(ids[:, 0] != 101) or np.any(ids[np.arange(len(ids)), lengths - 1] != 102):
        raise ValueError('TOKEN_BOUNDARY')
    if np.any(segments != 0):
        raise ValueError('SEGMENT_RULE')
    return {'rows': len(b), 'active_positions': int(active.sum()), 'unk100_active': int(((ids == 100) & active).sum()), 'rows_with_unk100': int(((ids == 100) & active).any(axis=1).sum())}


@torch.no_grad()
def replay(split, ordinals, encoder, model, norm, device):
    bert = np.asarray(split['text_bert'])[ordinals]
    original = np.asarray(split['text'], dtype=np.float32)[ordinals]
    stats = token_counts(bert)
    encoded = []
    for start in range(0, len(bert), 8):
        b = torch.as_tensor(bert[start:start + 8], dtype=torch.long, device=device)
        result = encoder(input_ids=b[:, 0], attention_mask=b[:, 1], token_type_ids=b[:, 2]).last_hidden_state
        encoded.append(result.cpu().numpy())
    encoded = np.concatenate(encoded).astype(np.float32)
    active = bert[:, 1] == 1
    delta = np.abs(encoded - original)
    criterion = delta <= (5e-4 + 1e-4 * np.abs(original))
    class_agreement = 0
    max_logits = 0.0
    max_regression = 0.0
    for j in range(len(ordinals)):
        s = active[j]
        base = {m: np.asarray(split[m][ordinals[j]], dtype=np.float32) for m in ('text', 'audio', 'vision')}
        alternative = dict(base, text=encoded[j])
        one = model(inputs_from_record(base, s, norm, device=device))
        two = model(inputs_from_record(alternative, s, norm, device=device))
        class_agreement += int(one['logits'].argmax() == two['logits'].argmax())
        max_logits = max(max_logits, float((one['logits'] - two['logits']).abs().max()))
        max_regression = max(max_regression, float((one['regression'] - two['regression']).abs().max()))
    return {**stats, 'ordinal_range': [int(ordinals[0]), int(ordinals[-1])], 'active_max_abs': float(delta[active].max()), 'active_mae': float(delta[active].mean()), 'active_relative_l2': float(np.linalg.norm((encoded - original)[active]) / np.linalg.norm(original[active])), 'active_allclose_backend_envelope_5e_4_1e_4': bool(criterion[active].all()), 'class_agreement': class_agreement, 'max_logits_delta': max_logits, 'max_regression_delta': max_regression}


def main():
    p = argparse.ArgumentParser()
    for key in ('a2', 'a3', 'encoder', 'checkpoint', 'output'):
        p.add_argument('--' + key, required=True)
    a = p.parse_args()
    output = Path(a.output)
    if output.exists():
        raise FileExistsError(output)
    if not torch.cuda.is_available():
        raise RuntimeError('GPU_REQUIRED_FOR_REGISTERED_REPLAY')
    device = 'cuda'
    with Path(a.a2).open('rb') as stream:
        data = pickle.load(stream)
    if not {'train', 'valid'} <= set(data):
        raise ValueError('A2_SPLIT_SCHEMA')
    original_state = model_state_hash(load_locked_model(a.checkpoint, device=device)[0])
    model, norm = load_locked_model(a.checkpoint, device=device)
    encoder = BertModel.from_pretrained(a.encoder, local_files_only=True).to(device).eval()
    encoder.requires_grad_(False)
    clean = {name: replay(data[name], ordinals, encoder, model, norm, device) for name, ordinals in {'train': np.arange(16, 80), 'valid': np.arange(8, 40)}.items()}
    full_counts = {name: token_counts(data[name]['text_bert']) for name in ('train', 'valid')}
    a3root = Path(a.a3).resolve()
    aligned = sorted([f for f in a3root.rglob('*.pkl') if f.parent.name.startswith('对齐')], key=lambda x: x.as_posix())
    if len(aligned) != 30:
        raise ValueError('A3_ALIGNED_COUNT')
    special = []
    for file in aligned:
        with file.open('rb') as stream:
            wrapper = pickle.load(stream)
        if set(wrapper) != {'test'}:
            raise ValueError('A3_WRAPPER')
        item = wrapper['test']
        special.append(token_counts(item['text_bert']))
    result = {'status': 'CLEAN_REPLAY_ONLY_SPECIAL_CORRUPTION_UNVERIFIED', 'a2_sha256': sha(a.a2), 'checkpoint_sha256': sha(a.checkpoint), 'encoder_model_sha256': sha(Path(a.encoder) / 'pytorch_model.bin'), 'device': device, 'criterion': {'atol': 5e-4, 'rtol': 1e-4, 'reason': 'fixed after same-weight CPU/GPU envelope observed on separate first replay; this expanded range was not used to choose tolerance'}, 'clean_expanded_replay': clean, 'a2_full_token_counts': full_counts, 'a3_aligned_token_counts': {'rows': sum(r['rows'] for r in special), 'active_positions': sum(r['active_positions'] for r in special), 'unk100_active': sum(r['unk100_active'] for r in special), 'rows_with_unk100': sum(r['rows_with_unk100'] for r in special)}, 'special_text_continuous_equivalence': 'UNKNOWN', 'special_missingness_rule_equivalence': 'UNKNOWN', 'original_model_unchanged': model_state_hash(model) == original_state, 'test_split_indexed': False, 'training_fits': 0}
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps({'status': result['status'], 'clean_expanded_replay': clean, 'a3_aligned_token_counts': result['a3_aligned_token_counts'], 'training_fits': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
