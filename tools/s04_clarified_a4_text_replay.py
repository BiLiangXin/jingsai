"""Read-only check of aligned Attachment4 continuous text coordinates."""
import argparse
import hashlib
import json
import pickle
from pathlib import Path

import numpy as np
import torch
from transformers import BertModel


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser()
    for key in ('source', 'encoder', 'output'):
        p.add_argument('--' + key, required=True)
    a = p.parse_args()
    output = Path(a.output)
    if output.exists():
        raise FileExistsError(output)
    root = Path(a.source).resolve()
    files = sorted(f for f in root.rglob('*.pkl') if f.parent.name.startswith('对齐'))
    if len(files) != 20:
        raise ValueError('A4_ALIGNED_COUNT')
    if not torch.cuda.is_available():
        raise RuntimeError('GPU_REQUIRED_FOR_REGISTERED_REPLAY')
    device = 'cuda'
    encoder = BertModel.from_pretrained(a.encoder, local_files_only=True).to(device).eval()
    encoder.requires_grad_(False)
    rows = []
    with torch.no_grad():
        for file in files:
            with file.open('rb') as stream:
                item = pickle.load(stream)
            bert = np.asarray(item['text_bert'])
            original = np.asarray(item['text'], dtype=np.float32)
            if bert.shape != (3, 50) or original.shape != (50, 768) or not np.isfinite(original).all():
                raise ValueError('A4_TEXT_SHAPE')
            if not np.isfinite(bert).all() or not np.array_equal(bert, np.round(bert)):
                raise ValueError('A4_TOKEN_VALUE')
            b = torch.as_tensor(bert[None], dtype=torch.long, device=device)
            generated = encoder(input_ids=b[:, 0], attention_mask=b[:, 1], token_type_ids=b[:, 2]).last_hidden_state[0].cpu().numpy()
            active = bert[1] == 1
            diff = np.abs(generated[active] - original[active])
            matched = bool(np.all(diff <= 5e-4 + 1e-4 * np.abs(original[active])))
            rows.append({'matched': matched, 'max_abs': float(diff.max()), 'mae': float(diff.mean()), 'active_positions': int(active.sum())})
    result = {'status': 'TEXT_FEATURE_POSITION_REPLAY', 'files': len(files), 'active_positions': sum(r['active_positions'] for r in rows), 'all_rows_match_backend_envelope': all(r['matched'] for r in rows), 'max_abs': max(r['max_abs'] for r in rows), 'mean_mae': float(np.mean([r['mae'] for r in rows])), 'encoder_model_sha256': sha(Path(a.encoder) / 'pytorch_model.bin'), 'criterion': {'atol': 5e-4, 'rtol': 1e-4, 'fixed_before_this_replay': True}, 'audio_vision_production_mapping': 'UNKNOWN', 'human_verified': 0, 'training_fits': 0}
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
