#!/usr/bin/env python3
"""Fetch only pinned code, tokenizer metadata and Kali TRAIN; never test/weights."""
import concurrent.futures
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import ssl
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / '.tools/benchkit'
REPORT = ROOT / 'docs/verification/benchkit-source-preparation.json'
KALI = '0b5bf54c9e343f94e113874b98ff5de815780328'
ATHENA = '39d3a74eaf84b93e21dde0a4b60ddd4f08620eaf'
MODELS = {
    'cisco': ('fdtn-ai/Foundation-Sec-8B-Reasoning', '63c930c82d7646226d33502bec5870019738400e'),
    'redsage': ('RISys-Lab/RedSage-K-SFT-GRPO', '843e2e3096e7de68f5c35eb16238f4909f21695a'),
}


def fetch(url):
    ctx = ssl.create_default_context(cafile='/etc/ssl/cert.pem')
    req = urllib.request.Request(url, headers={'User-Agent': 'Minhao-academic-benchkit/1.0'})
    with urllib.request.urlopen(req, context=ctx, timeout=35) as res:
        raw = res.read(32_000_001)
    if len(raw) > 32_000_000:
        raise ValueError('Bounded download exceeded 32MB')
    if raw.startswith(b'version https://git-lfs.github.com/spec/'):
        raise ValueError('LFS pointer instead of artifact')
    return raw


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    tasks = []
    for p in ['src/model_score.py', 'src/prompt.py', 'src/prompt_builder.py',
              'src/io_utils.py', 'src/evaluate.py', 'src/vllm_inference.py',
              'src/vllm_runtime.py', 'src/prediction_checkpoint.py',
              'src/train/sft_kalibench.py', 'src/train/grpo_kalibench.py',
              'Scoring/model_score.py', 'src/scoring_pipeline.py', 'docs/evaluation.md', 'docs/training.md',
              'docs/reference.md', 'README.md', 'requirements.txt', 'pages/README.md',
              'KaliBench_data/kalibench_verified_train_3504.jsonl']:
        tasks.append((f'kali/{p}', f'https://raw.githubusercontent.com/RISys-Lab/KaliBench/{KALI}/{p}'))
    for p in ['athena_eval/taa/aliases.csv', 'athena_eval/taa/related_groups.csv']:
        tasks.append((f'athena/{p}', f'https://raw.githubusercontent.com/Athena-Software-Group/athenabench/{ATHENA}/{p}'))
    tasks += [
        ('docs/openssl-dgst.html', 'https://docs.openssl.org/3.5/man1/openssl-dgst/'),
        ('docs/openssl-x509.html', 'https://docs.openssl.org/3.5/man1/openssl-x509/'),
        ('docs/tshark.html', 'https://www.wireshark.org/docs/man-pages/tshark.html'),
        ('docs/tcpdump.html', 'https://www.tcpdump.org/manpages/tcpdump.1.html'),
        ('docs/jq.html', 'https://jqlang.org/manual/'),
        ('docs/coreutils.html', 'https://www.gnu.org/software/coreutils/manual/coreutils.html'),
        ('docs/ss.html', 'https://man7.org/linux/man-pages/man8/ss.8.html'),
        ('docs/grep.html', 'https://www.gnu.org/software/grep/manual/grep.html'),
    ]
    metadata = {}
    failures = []
    for alias, (model, rev) in MODELS.items():
        try:
            api = f'https://huggingface.co/api/models/{model}/revision/{rev}'
            raw = fetch(api)
            info = json.loads(raw)
            if info['sha'] != rev or info.get('private') or info.get('gated'):
                raise ValueError('Unexpected revision or private/gated checkpoint')
            path = DEST / 'models' / alias / 'metadata.json'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            metadata[alias] = {'id': model, 'revision': rev,
                               'license_card_field': info.get('cardData', {}).get('license'),
                               'weight_files': [x['rfilename'] for x in info.get('siblings', []) if x['rfilename'].endswith('.safetensors')]}
            available = {x['rfilename'] for x in info.get('siblings', [])}
            wanted = ['tokenizer.json', 'tokenizer_config.json', 'config.json',
                      'generation_config.json', 'special_tokens_map.json',
                      'chat_template.jinja', 'README.md']
            wanted += sorted(x for x in available if '/' not in x and ('license' in x.lower() or 'notice' in x.lower()))
            for p in dict.fromkeys(wanted):
                if p in available:
                    tasks.append((f'models/{alias}/{p}', f'https://huggingface.co/{model}/resolve/{rev}/{p}'))
        except Exception as exc:
            failures.append({'artifact': f'models/{alias}/metadata', 'error': type(exc).__name__})

    def one(task):
        relative, url = task
        if 'test_5000' in relative or relative.endswith('.safetensors'):
            raise ValueError('Download allowlist violation')
        path = DEST / relative
        try:
            raw = path.read_bytes() if path.exists() else fetch(url)
            if relative.endswith('.json'):
                json.loads(raw)
            if relative.endswith('.jsonl'):
                rows = [json.loads(x) for x in raw.splitlines() if x.strip()]
                if len(rows) != 3504:
                    raise ValueError('Unexpected train count')
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            return {'path': str(path.relative_to(ROOT)), 'url': url,
                    'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
        except Exception as exc:
            return {'artifact': relative, 'url': url, 'error': type(exc).__name__}

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        outputs = list(pool.map(one, tasks))
    good = [x for x in outputs if 'sha256' in x]
    failures += [x for x in outputs if 'sha256' not in x]
    report = {'checked_at_utc': datetime.now(timezone.utc).isoformat(),
              'status': 'COMPLETE' if not failures else 'PARTIAL',
              'code_revisions': {'athena': ATHENA, 'kali': KALI},
              'models': metadata, 'files': good, 'failures': failures,
              'official_test_files_downloaded': 0, 'model_weights_downloaded': 0,
              'code_executed_by_fetcher': False,
              'kali_train_status': 'TRAIN_ONLY_SOURCE_LABELS_NOT_INDEPENDENTLY_AUDITED'}
    REPORT.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'files': len(good), 'models': metadata,
                      'failures': failures, 'report': str(REPORT)}, indent=2))
    return 0 if not failures else 1


if __name__ == '__main__':
    raise SystemExit(main())
