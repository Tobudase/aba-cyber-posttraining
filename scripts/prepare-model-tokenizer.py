#!/usr/bin/env python3
"""Download pinned public tokenizer/config files only; never model weights."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import ssl
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
MODEL = 'Qwen/Qwen3-8B'
REVISION = 'b968826d9c46dd6066d109eabc6255188de91218'
FILES = ('config.json', 'generation_config.json', 'tokenizer_config.json', 'tokenizer.json', 'LICENSE')
MAX_FILE_BYTES = 20 * 1024 * 1024


def get(url):
    context = ssl.create_default_context()
    if not Path(ssl.get_default_verify_paths().cafile or '').is_file() and Path('/etc/ssl/cert.pem').is_file():
        context.load_verify_locations('/etc/ssl/cert.pem')
    request = urllib.request.Request(url, headers={'User-Agent': 'UCSD-public-model-metadata/1.0'})
    with urllib.request.urlopen(request, timeout=40, context=context) as response:
        data = response.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise RuntimeError('Download exceeded file bound')
    return data


def main():
    metadata = json.loads(get(f'https://huggingface.co/api/models/{MODEL}/revision/{REVISION}'))
    if metadata['sha'] != REVISION or metadata['id'] != MODEL or metadata.get('gated'):
        raise RuntimeError('Pinned public model metadata mismatch')
    dest = ROOT / '.tools/model-tokenizer' / ('qwen3-8b-' + REVISION[:12])
    dest.mkdir(parents=True, exist_ok=True)
    files = {}
    total = 0
    for name in FILES:
        raw = get(f'https://huggingface.co/{MODEL}/resolve/{REVISION}/{name}')
        total += len(raw)
        if total > 32 * 1024 * 1024:
            raise RuntimeError('Total download bound exceeded')
        if name.endswith('.json'):
            json.loads(raw)
        (dest / name).write_bytes(raw)
        files[name] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    tokenizer = json.loads((dest / 'tokenizer_config.json').read_text())
    model_config = json.loads((dest / 'config.json').read_text())
    if model_config.get('model_type') != 'qwen3' or not tokenizer.get('chat_template'):
        raise RuntimeError('Unexpected model/tokenizer structure')
    lock = {'status': 'CANDIDATE_PINNED_TOKENIZER_ONLY_NOT_TRAINED',
            'checked_at': datetime.now(timezone.utc).isoformat(), 'model_id': MODEL, 'revision': REVISION,
            'license': metadata.get('cardData', {}).get('license'),
            'parameters': metadata.get('safetensors', {}).get('total'),
            'local_tokenizer_dir': dest.relative_to(ROOT).as_posix(), 'files': files,
            'model_weights_downloaded': False, 'trust_remote_code': False,
            'official_template_has_generation_tags': '{% generation' in tokenizer['chat_template'] or '{%- generation' in tokenizer['chat_template'],
            'notes': ['Tokenizer/config cache is excluded from handoff; rerun this script to restore the exact pinned revision.',
                      'Original chat template needs a verified assistant-mask training template before assistant-only SFT.']}
    path = ROOT / 'configs/student-model.lock.json'
    path.write_text(json.dumps(lock, indent=2) + '\n')
    print(json.dumps({'lock': str(path), 'model': MODEL, 'revision': REVISION,
                      'downloaded_bytes': total, 'weights_downloaded': False,
                      'official_template_has_generation_tags': lock['official_template_has_generation_tags']}, indent=2))


if __name__ == '__main__':
    main()
