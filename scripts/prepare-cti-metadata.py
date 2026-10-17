#!/usr/bin/env python3
"""Pin public CTI candidate metadata without fetching test rows or weights."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT/'.tools/cti-review'
CACHE.mkdir(parents=True, exist_ok=True)


def fetch(name, url):
    # curl uses the platform CA store; TLS verification remains enabled.
    response = subprocess.run(['curl', '--fail', '--silent', '--show-error',
                               '--location', '--max-time', '45',
                               '--user-agent', 'Minhao-CTI-research-preparation', url],
                              capture_output=True, check=True)
    raw = response.stdout
    if len(raw) > 4_000_000:
        raise ValueError('Metadata response too large')
    data = json.loads(raw)
    (CACHE/(name+'.json')).write_text(json.dumps(data, indent=2)+'\n')
    return name, data


def main():
    urls = {
        'faith_commit': 'https://api.github.com/repos/cisco-foundation-ai/faith/commits/main',
        'cti_commit': 'https://api.github.com/repos/maveryn/cti-bench/commits/main',
        'cisco_model': 'https://huggingface.co/api/models/fdtn-ai/Foundation-Sec-8B-Reasoning?blobs=true',
        'qwen14_model': 'https://huggingface.co/api/models/Qwen/Qwen3-14B?blobs=true',
        'qwen8_model': 'https://huggingface.co/api/models/Qwen/Qwen3-8B?blobs=true',
        'qwen38_model': 'https://huggingface.co/api/models/Qwen/Qwen3.8-27B?blobs=true',
        'cisco_gguf_model': 'https://huggingface.co/api/models/fdtn-ai/Foundation-Sec-8B-Reasoning-Q4_K_M-GGUF?blobs=true',
        'cti_dataset': 'https://huggingface.co/api/datasets/AI4Sec/cti-bench?blobs=true',
    }
    with ThreadPoolExecutor(4) as pool:
        results = dict(pool.map(lambda item: fetch(*item), urls.items()))
    lock = {'checked_at_utc': datetime.now(timezone.utc).isoformat(),
            'status': 'CANDIDATES_NOT_RESEARCH_SELECTION',
            'official_test_rows_downloaded': False, 'weights_downloaded': False,
            'repositories': {}, 'models': {}, 'dataset': {}}
    for name, repo in [('faith', 'cisco-foundation-ai/faith'), ('cti', 'maveryn/cti-bench')]:
        revision = results[name+'_commit']['sha']
        _, tree = fetch(name+'_tree', f'https://api.github.com/repos/{repo}/git/trees/{revision}?recursive=1')
        lock['repositories'][name] = {'id': repo, 'revision': revision,
                                      'tree_entries': len(tree['tree'])}
    for name in ('cisco_model', 'qwen14_model', 'qwen8_model', 'qwen38_model', 'cisco_gguf_model'):
        model = results[name]
        weights = [f for f in model['siblings'] if f['rfilename'].endswith(('.safetensors','.gguf'))]
        lock['models'][name] = {
            'id': model['id'], 'revision': model['sha'], 'gated': model.get('gated'),
            'license_metadata': model.get('cardData', {}).get('license'),
            'safetensors': model.get('safetensors'),
            'weight_files': [{k: x[k] for k in ('rfilename', 'size', 'lfs') if k in x} for x in weights],
            'weight_bytes': sum(x.get('size', 0) for x in weights),
        }
        if name=='cisco_gguf_model':
            lock['models'][name]['role']='OFFICIAL_QUANTIZED_ENGINEERING_ONLY_NOT_BF16_BASELINE'
            lock['models'][name]['underlying_bf16_revision_proven_by_quantized_release']=False
    dataset = results['cti_dataset']
    lock['dataset'] = {'id': dataset['id'], 'revision': dataset['sha'],
                       'license_metadata': dataset.get('cardData', {}).get('license'),
                       'official_use': 'EVALUATION_ONLY', 'rows_downloaded': False}
    lock['cached_metadata_sha256'] = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in CACHE.glob('*.json')
        if p.name in {name+'.json' for name in urls}|{'faith_tree.json', 'cti_tree.json'}}
    destination = ROOT/'configs/cti-candidates.lock.json'
    destination.write_text(json.dumps(lock, indent=2)+'\n')
    print(json.dumps({'lock': str(destination), 'repositories': lock['repositories'],
                      'models': {k: {f: v[f] for f in ('id', 'revision', 'gated', 'license_metadata', 'weight_bytes')} for k, v in lock['models'].items()},
                      'dataset': lock['dataset']}, indent=2))


if __name__ == '__main__':
    main()
