"""Release contracts and atomic file operations (single writer)."""
import hashlib
import json
import math
import os
import re
import tempfile
from pathlib import Path


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()


def cache_key(data_path, config):
    return sha(canonical({'data_sha256': sha(Path(data_path).read_bytes()), 'config': config}))


def validate_release(manifest, report):
    try:
        if type(manifest['schema_version']) is not int or manifest['schema_version'] != 1:
            raise ValueError('schema')
        for key in ('model_id', 'artifact_uri'):
            if not isinstance(manifest[key], str) or not manifest[key].strip(): raise ValueError(key)
        for key in ('model_sha256', 'protocol_sha256', 'golden_sha256', 'runtime_sha256'):
            if not isinstance(manifest[key], str) or not re.fullmatch(r'[0-9a-f]{64}', manifest[key]): raise ValueError(key)
        if not isinstance(manifest['runtime'], dict) or not manifest['runtime'] or sha(canonical(manifest['runtime'])) != manifest['runtime_sha256']:
            raise ValueError('runtime')
        if report['status'] != 'complete' or report['passed'] is not True: raise ValueError('gate')
        if not isinstance(report['evaluation_run_id'], str) or not report['evaluation_run_id'].strip(): raise ValueError('evaluation_run_id')
        for key in ('model_id', 'model_sha256', 'protocol_sha256', 'golden_sha256', 'runtime_sha256'):
            if report[key] != manifest[key]: raise ValueError('mismatch: '+key)
        for key in ('accuracy', 'format_rate'):
            v = report['metrics'][key]
            if type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1: raise ValueError(key)
    except (KeyError, TypeError, OverflowError) as e:
        raise ValueError('incomplete release') from e


def verify_files(manifest, root):
    files = manifest.get('file_hashes')
    if not isinstance(files, dict) or not files: raise ValueError('missing file hashes')
    root = Path(root).resolve()
    for name, expected in files.items():
        path = root / name
        if Path(name).is_absolute() or '..' in Path(name).parts or not path.is_file() or file_sha(path) != expected:
            raise ValueError('artifact changed: '+name)
    if sha(canonical(files)) != manifest['model_sha256']: raise ValueError('model hash mismatch')


def atomic_json(target, value):
    target = Path(target); target.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, suffix='.tmp', delete=False) as f:
            name = f.name
            f.write(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False).encode())
            f.flush(); os.fsync(f.fileno())
        os.replace(name, target)
    finally:
        if name and os.path.exists(name): os.unlink(name)


def publish(manifest, report, target):
    validate_release(manifest, report)
    atomic_json(target, manifest)
