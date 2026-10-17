#!/usr/bin/env python3
"""Run Cisco's official quantized model on authored CTI integration examples.

Uses an isolated localhost-only Ollama instance and model store; never touches
the user's existing Ollama service/models. No official benchmark data, model
training, hosted inference or credentials. Run with the pinned FAITH venv.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.request

from jinja2 import Environment, StrictUndefined
from transformers import AutoTokenizer
from cti_native_metrics import ROOT, final_answer, grade, json_default

parser = argparse.ArgumentParser()
parser.add_argument('--limit', type=int, default=48)
parser.add_argument('--max-output-tokens', type=int, default=512)
parser.add_argument('--attempt', type=int, default=1)
parser.add_argument('--one-per-group', action='store_true')
parser.add_argument('--record-ids',help='Comma-separated fixture IDs for a disclosed follow-up subset')
args = parser.parse_args()
assert 1 <= args.limit <= 48 and args.max_output_tokens in (512, 1024)
assert 1 <= args.attempt <= 5
name = f'cti-local-pilot-{args.attempt}'
out = ROOT/'docs/verification'/name
download = json.loads((ROOT/'docs/verification/cti-cisco_gguf_model-download.json').read_text())
assert download['status'] == 'PASSED'
directory = Path(download['directory'])
gguf = next(directory.glob('*.gguf'))
weight_hasher = hashlib.sha256()
with gguf.open('rb') as source:
    for block in iter(lambda: source.read(8*1024*1024), b''):
        weight_hasher.update(block)
assert weight_hasher.hexdigest() == download['files'][gguf.name]['sha256']
out.mkdir(exist_ok=False)
model_config = json.loads((directory/'tokenizer_config.json').read_text())
tokenizer = AutoTokenizer.from_pretrained(directory,local_files_only=True,trust_remote_code=False)
template = Environment(undefined=StrictUndefined).from_string(model_config['chat_template'])
fixture = ROOT/'data/synthetic/cti-rcm-fixture/examples.jsonl'
rows = [json.loads(line) for line in fixture.read_text().splitlines()]
if args.one_per_group:
    rows=rows[::2]
if args.record_ids:
    identifiers=args.record_ids.split(',')
    assert len(identifiers)==len(set(identifiers)) and set(identifiers)<={r['id'] for r in rows}
    rows=[r for r in rows if r['id'] in identifiers]
rows=rows[:args.limit]
assert all(row['synthetic_only'] and not row['training_eligible'] for row in rows)
home = ROOT/'.tools/cti-ollama-home'
home.mkdir(mode=0o700, exist_ok=True)
(home/'models').mkdir(exist_ok=True)
with socket.socket() as bound:
    bound.bind(('127.0.0.1', 0))
    port = bound.getsockname()[1]
base_url = f'http://127.0.0.1:{port}'
assert (Path.home()/'.ollama/id_ed25519').is_file(), 'Existing Ollama identity required; do not create global state'
env = {'PATH': os.defpath+':/opt/homebrew/bin', 'HOME': os.environ['HOME'],
       'TMPDIR': str(ROOT/'.tools'), 'OLLAMA_MODELS': str(home/'models'),
       'OLLAMA_HOST': f'127.0.0.1:{port}', 'OLLAMA_NO_CLOUD': '1',
       'OLLAMA_NUM_PARALLEL': '1', 'OLLAMA_MAX_LOADED_MODELS': '1',
       'OLLAMA_KEEP_ALIVE': '2m', 'OLLAMA_CONTEXT_LENGTH': '2048'}
model_name = 'cti-cisco8-q4-engineering'
modelfile = home/'Modelfile'
modelfile.write_text(f'FROM {gguf}\nPARAMETER num_ctx 2048\nPARAMETER temperature 0\nPARAMETER stop "<|end_of_text|>"\n')
service_log = (ROOT/'.tools/cti-review'/f'{name}-ollama.log').open('x')
service = subprocess.Popen(['/opt/homebrew/bin/ollama', 'serve'], env=env,
                           stdout=service_log, stderr=subprocess.STDOUT,
                           start_new_session=True)
start = time.monotonic()
results = []
server_version = None
runtime_error = None
gpu_info = None


def request(path, data=None, timeout=180):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(base_url+path, data=body,
                                 headers={'Content-Type': 'application/json'})
    # Never send localhost traffic through configured external proxies.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=timeout) as response:
        return json.loads(response.read(2_000_000))


def hard_deadline(signum, frame):
    raise TimeoutError('Local pilot reached its 25-minute hard deadline')


signal.signal(signal.SIGALRM, hard_deadline)
signal.alarm(1500)
try:
    for _ in range(60):
        if service.poll() is not None:
            raise RuntimeError('Private Ollama service exited; see local service log')
        try:
            server_version = request('/api/version', timeout=2)
            break
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.5)
    assert server_version, 'Local Ollama failed readiness'
    created = subprocess.run(['/opt/homebrew/bin/ollama', 'create', model_name,
                              '-f', str(modelfile)], env=env,
                             capture_output=True, text=True, timeout=180)
    (ROOT/'.tools/cti-review'/f'{name}-import.log').write_text(created.stdout+created.stderr)
    assert created.returncode == 0, 'GGUF import failed; inspect local import log'
    for index, row in enumerate(rows):
        description = row['description']
        instruction = ('Analyze the following CVE description and map it to the appropriate CWE. '
                       'Provide a brief justification for your choice. Ensure the last line '
                       'of your response contains only the CWE ID.')
        user = instruction+'\n\nCVE Description: '+description
        prompt = template.render(messages=[{'role': 'user', 'content': user}],
                                 bos_token=model_config['bos_token'],
                                 eos_token=model_config['eos_token'], add_generation_prompt=True)
        assert prompt.rstrip().endswith('<think>')
        canonical_prompt=prompt
        # This GGUF makes llama.cpp insert BOS automatically. The first smoke
        # exposed a duplicated BOS when the textual template also included it.
        assert prompt.startswith(model_config['bos_token'])
        prompt=prompt[len(model_config['bos_token']):]
        expected_prompt_tokens=len(tokenizer.encode(canonical_prompt,add_special_tokens=False))
        before = time.monotonic()
        response = request('/api/generate', {
            'model': model_name, 'prompt': prompt, 'raw': True, 'stream': False,
            'keep_alive': '2m', 'options': {'temperature': 0, 'seed': 42,
             'num_ctx': 2048, 'num_predict': args.max_output_tokens,
             'num_thread': 4}}, timeout=180)
        text = response.get('response', '')
        item = {'id': row['id'], 'group': row['group'], 'description': description,
                'label': row['label'], 'synthetic_only': True,
                'training_eligible': False, 'answer_text': final_answer(text, True),
                'response_sha256': hashlib.sha256(text.encode()).hexdigest(),
                'raw_response': text, 'reasoning_completed': '</think>' in text,
                'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(),
                'canonical_prompt_sha256': hashlib.sha256(canonical_prompt.encode()).hexdigest(),
                'canonical_prompt_tokens':expected_prompt_tokens,
                'transport_bos_removed_for_gguf_auto_bos':True,
                'wall_seconds': time.monotonic()-before,
                'prompt_tokens': response.get('prompt_eval_count'),
                'output_tokens': response.get('eval_count', 0),
                'truncated': response.get('done_reason') == 'length' or
                    response.get('eval_count', 0) >= args.max_output_tokens,
                'done_reason': response.get('done_reason'),
                'load_duration_ns': response.get('load_duration'),
                'eval_duration_ns': response.get('eval_duration'),
                'prompt_eval_duration_ns': response.get('prompt_eval_duration')}
        results.append(item)
        with (out/'responses.jsonl').open('a') as f:
            f.write(json.dumps(item)+'\n')
        if index==0:
            assert response.get('prompt_eval_count')==expected_prompt_tokens, 'Fresh runtime token count differs from canonical template'
        if index == 0:
            gpu_info = request('/api/ps')
        print(json.dumps({'completed': len(results), 'id': row['id'],
                          'tokens': item['output_tokens'], 'seconds': round(item['wall_seconds'], 2),
                          'reasoning_completed': item['reasoning_completed']}), flush=True)
except Exception as error:
    runtime_error = f'{type(error).__name__}: {error}'
finally:
    signal.alarm(0)
    try:
        if server_version and service.poll() is None:
            request('/api/generate', {'model': model_name, 'keep_alive': 0}, timeout=15)
    except Exception:
        pass
    if service.poll() is None:
        os.killpg(service.pid, signal.SIGTERM)
        try:
            service.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(service.pid, signal.SIGKILL)
            service.wait(timeout=5)
    service_log.close()

metrics, details = grade(results) if results else ({}, [])
import numpy as np
latencies = [r['wall_seconds'] for r in results]
report = {'checked_at_utc': datetime.now(timezone.utc).isoformat(),
          'status': 'COMPLETED' if runtime_error is None and len(results)==len(rows) else 'FAILED_PARTIAL',
          'model_id': download['model_id'], 'revision': download['revision'],
          'weight_sha256': download['files'][gguf.name]['sha256'],
          'quantization': 'Official Q4_K_M GGUF', 'runtime': server_version,
          'runtime_model_state': gpu_info, 'hardware': 'Apple M2 Pro, 16GiB unified RAM',
          'context_tokens': 2048, 'max_output_tokens': args.max_output_tokens,
          'temperature': 0, 'seed': 42, 'raw_prompt': True,
          'transport_bos_removed_for_gguf_auto_bos':True,
          'one_per_mechanism':args.one_per_group,
          'requested_fixture_ids':args.record_ids.split(',') if args.record_ids else None,
          'chat_template_sha256': hashlib.sha256(model_config['chat_template'].encode()).hexdigest(),
          'fixture_sha256': hashlib.sha256(fixture.read_bytes()).hexdigest(),
          'requested_records': len(rows), 'completed_records': len(results),
          'completion_rate': len(results)/len(rows),
          'all_requested_record_accuracy': sum(x['strict_correct'] for x in details)/len(rows),
          'synthetic_only': True, 'official_test_records': 0, 'training_executed': False,
          'metrics_are_not_benchmark_scores': True,
          'latency_seconds': {'median': float(np.median(latencies)),
                              'p95': float(np.percentile(latencies, 95)),
                              'mean': float(np.mean(latencies))} if latencies else {},
          'elapsed_seconds_including_setup': time.monotonic()-start,
          'native_faith_metrics': metrics, 'graded_records': details,
          'runtime_error': runtime_error, 'private_service_stopped': service.poll() is not None,
          'existing_ollama_state_modified': False,
          'limitations': ['Quantized Mac engineering fixture, not BF16/GPU baseline',
                         '48 simple authored examples with paired paraphrases and non-independent labels',
                         'Short synthetic prompts do not establish official-test throughput',
                         'Inference token cap/mode differs from the published five-trial protocol']}
(out/'result.json').write_text(json.dumps(report, indent=2, default=json_default)+'\n')
print(json.dumps({'status': report['status'], 'records': len(results),
                  'report': str(out/'result.json'), 'error': runtime_error,
                  'private_service_stopped': report['private_service_stopped']}, indent=2))
raise SystemExit(0 if report['status']=='COMPLETED' else 1)
