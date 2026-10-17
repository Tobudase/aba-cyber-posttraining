#!/usr/bin/env python3
"""Download one pinned public candidate, verify HF LFS hashes, never run code."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import ssl
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--model-key', choices=['cisco_model', 'qwen8_model', 'cisco_gguf_model'], default='cisco_model')
parser.add_argument('--parallel-weight-chunks', action='store_true')
parser.add_argument('--xet', action='store_true')
args = parser.parse_args()
lock = json.loads((ROOT/'configs/cti-candidates.lock.json').read_text())
candidate = lock['models'][args.model_key]
metadata_path = ROOT/f'.tools/cti-review/{args.model_key}.json'
if not metadata_path.exists():
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    url = f'https://huggingface.co/api/models/{candidate["id"]}/revision/{candidate["revision"]}?blobs=true'
    raw = subprocess.check_output(['curl','--fail','--silent','--show-error','--location','--max-time','45',url])
    assert len(raw) < 4_000_000
    fetched = json.loads(raw)
    assert fetched['sha'] == candidate['revision']
    metadata_path.write_bytes(raw)
metadata = json.loads(metadata_path.read_text())
if args.model_key == 'cisco_gguf_model':
    candidate = {'id': metadata['id'], 'revision': metadata['sha'],
                 'weight_bytes': sum(x.get('size', 0) for x in metadata['siblings'] if x['rfilename'].endswith('.gguf'))}
else:
    candidate = lock['models'][args.model_key]
assert metadata['sha'] == candidate['revision'] and not metadata.get('gated')
assert candidate['weight_bytes'] < 18_000_000_000
assert shutil.disk_usage(ROOT).free > 35_000_000_000
dest = ROOT/'.tools/cti-models'/args.model_key/candidate['revision']
dest.mkdir(parents=True, exist_ok=True)
small = {'config.json', 'generation_config.json', 'tokenizer.json', 'tokenizer_config.json',
         'special_tokens_map.json', 'model.safetensors.index.json', 'README.md', 'NOTICE.md',
         'LICENSE', 'LICENSE_APACHE2.md', 'LICENSE_LLAMA31.md', 'chat_template.jinja', 'vocab.json', 'merges.txt'}
files = [item for item in metadata['siblings'] if item['rfilename'] in small or item['rfilename'].endswith(('.safetensors', '.gguf'))]
start = time.monotonic()


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8*1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def ranged_download(url, temporary, size):
    """Resume four disjoint public ranges; verify the complete LFS hash later."""
    chunk_size = (size+3)//4
    chunks = temporary.parent/(temporary.name+'.chunks')
    chunks.mkdir(exist_ok=True)
    # Preserve existing contiguous bytes, including an earlier single download.
    if temporary.exists():
        with temporary.open('rb') as source:
            for index in range(4):
                remaining = min(chunk_size, size-index*chunk_size)
                target = chunks/str(index)
                if remaining <= 0:
                    break
                with target.open('wb') as output:
                    while remaining:
                        block = source.read(min(8*1024*1024, remaining))
                        if not block:
                            break
                        output.write(block)
                        remaining -= len(block)
                if remaining:
                    break
        temporary.unlink()
    ca = subprocess.check_output([str(ROOT/'.tools/cti-faith-venv/bin/python'),
                                  '-c', 'import certifi; print(certifi.where())'], text=True).strip()
    context = ssl.create_default_context(cafile=ca)

    def get_chunk(index):
        first = index*chunk_size
        last = min(size, first+chunk_size)-1
        path = chunks/str(index)
        already = path.stat().st_size if path.exists() else 0
        assert already <= last-first+1
        if already == last-first+1:
            return
        first += already
        req = urllib.request.Request(url, headers={'Range': f'bytes={first}-{last}',
                                                   'User-Agent': 'Minhao-CTI-research-preparation'})
        deadline = time.monotonic()+1200
        with urllib.request.urlopen(req, context=context, timeout=60) as response:
            assert response.status == 206, 'Server did not honor byte ranges'
            assert response.headers.get('Content-Range') == f'bytes {first}-{last}/{size}'
            with path.open('ab') as output:
                while block := response.read(4*1024*1024):
                    assert time.monotonic() < deadline, 'Range deadline exceeded'
                    assert output.tell()+len(block) <= last-index*chunk_size+1
                    output.write(block)
        assert path.stat().st_size == last-index*chunk_size+1
        print(f'RANGE_COMPLETE {index}', flush=True)

    with ThreadPoolExecutor(4) as pool:
        list(pool.map(get_chunk, range(4)))
    with temporary.open('wb') as output:
        for index in range(4):
            with (chunks/str(index)).open('rb') as source:
                shutil.copyfileobj(source, output, length=8*1024*1024)
    assert temporary.stat().st_size == size


def download(item):
    name = item['rfilename']
    assert '/' not in name and not name.startswith('.')
    target = dest/name
    expected_hash = item.get('lfs', {}).get('sha256')
    expected_bytes = item.get('size')
    if target.exists() and target.stat().st_size == expected_bytes:
        digest = sha256(target)
        if not expected_hash or digest == expected_hash:
            return name, {'bytes': target.stat().st_size, 'sha256': digest,
                          'lfs_sha256_verified': bool(expected_hash), 'reused': True}
    temporary = target.with_suffix(target.suffix+'.partial')
    url = f'https://huggingface.co/{candidate["id"]}/resolve/{candidate["revision"]}/{name}'
    if args.xet and name.endswith('.gguf'):
        import os
        os.environ['HF_HOME'] = str(ROOT/'.tools/cti-hf-cache')
        os.environ['HF_HUB_DISABLE_IMPLICIT_TOKEN'] = '1'
        os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
        os.environ['HF_HUB_DOWNLOAD_TIMEOUT'] = '60'
        from huggingface_hub import hf_hub_download
        result = hf_hub_download(candidate['id'], name, revision=candidate['revision'],
                                 token=False, local_dir=str(dest))
        assert Path(result).resolve() == target.resolve()
        if expected_bytes is not None:
            assert target.stat().st_size == expected_bytes
        digest = sha256(target)
        assert digest == expected_hash, name+' LFS hash mismatch'
        print('VERIFIED '+name+' via native Xet backend', flush=True)
        return name, {'bytes':target.stat().st_size,'sha256':digest,
                      'lfs_sha256_verified':True,'reused':False,'transport':'huggingface_hub_native_xet'}
    if args.parallel_weight_chunks and name.endswith('.gguf'):
        ranged_download(url, temporary, expected_bytes)
    else:
        subprocess.run(['curl', '--fail', '--silent', '--show-error', '--location',
                        '--connect-timeout', '20', '--max-time', '1200', '--retry', '1',
                        '--continue-at', '-', '--output', str(temporary), url], check=True)
    if expected_bytes is not None:
        assert temporary.stat().st_size == expected_bytes, name+' size mismatch'
    digest = sha256(temporary)
    if expected_hash:
        assert digest == expected_hash, name+' LFS hash mismatch'
    temporary.replace(target)
    chunks = temporary.parent/(temporary.name+'.chunks')
    if chunks.is_dir():
        for part in chunks.iterdir():
            assert part.name in {'0','1','2','3'} and part.is_file()
            part.unlink()
        chunks.rmdir()
    print('VERIFIED '+name, flush=True)
    return name, {'bytes': target.stat().st_size, 'sha256': digest,
                  'lfs_sha256_verified': bool(expected_hash), 'reused': False}


with ThreadPoolExecutor(3) as pool:
    records = dict(pool.map(download, files))
report = {'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'status': 'PASSED',
          'model_id': candidate['id'], 'revision': candidate['revision'],
          'directory': str(dest), 'elapsed_seconds': time.monotonic()-start,
          'files': records, 'remote_code_executed': False,
          'official_test_data_downloaded': False}
path = ROOT/f'docs/verification/cti-{args.model_key}-download.json'
path.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({'status': 'PASSED', 'report': str(path), 'directory': str(dest)}, indent=2))
