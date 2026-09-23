"""Record the code actually present at experiment start, not only the later report commit."""
from __future__ import annotations
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
from datetime import datetime, timezone


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def experiment_provenance(root: Path, config_path: Path, inputs: list[Path], seed: int,
                          split: str, data_kind: str = 'official') -> dict:
    """Inputs must be trusted files; this hashes bytes but never unpickles them."""
    if data_kind not in {'official', 'synthetic', 'none'} or split not in {'train', 'valid', 'test', 'special', 'engineering'}:
        raise ValueError('Invalid provenance domain/split.')
    root = root.resolve()
    def g(*args):
        p = subprocess.run(['git', *args], cwd=root, capture_output=True, text=True, check=True)
        return p.stdout.strip()
    packages = {}
    for name in ['numpy', 'torch', 'transformers', 'opensmile', 'captum', 'scikit-learn']:
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    source = []
    for path in sorted((root / 'src').rglob('*.py')):
        if path.is_symlink():
            raise ValueError('Source symlinks require explicit review.')
        source.append({'path': path.relative_to(root).as_posix(), 'sha256': file_sha256(path)})
    return {'captured_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'data_kind': data_kind, 'split': split, 'seed': seed,
            'git_head_at_experiment_start': g('rev-parse', 'HEAD'),
            'working_tree_dirty': bool(g('status', '--porcelain')),
            'source_files_at_experiment_start': source,
            'config': {'name': config_path.name, 'sha256': file_sha256(config_path)},
            'inputs': [{'name': p.name, 'bytes': p.stat().st_size, 'sha256': file_sha256(p)} for p in inputs],
            'python': platform.python_version(), 'os': platform.system(), 'architecture': platform.machine(),
            'package_versions': packages,
            'note': 'No hostname, username, credentials, absolute data paths, or environment dump is included.'}
