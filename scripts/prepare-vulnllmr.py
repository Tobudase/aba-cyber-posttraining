#!/usr/bin/env python3
"""Prepare pinned public metadata and four train-only engineering examples."""
import ast
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL = 'Virtue-AI-HUB/VulnLLM-R-7B'
REV = '8cd13d7a35f13b187102dba166413d4450836a40'
CODE = '5357371a2271df1048666220415a3bc937af5f9d'
TRAIN_PATH = 'datasets/train/function_level/python/CWE-327.json'
TRAIN_SHA = '9055a43bbf5b7041892cdcbade8a120af1d1808b08126db13eecc7a8dee1e712'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fetch(url, dest):
    data = subprocess.check_output(['curl', '--fail', '--location', '--silent', '--show-error',
                                   '--max-time', '60', '--max-filesize', '30000000', url])
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return data


def main():
    cache = ROOT / '.tools/model-tokenizer/vulnllmr-7b-8cd13d7a35f1'
    artifacts = {}
    for name in ['config.json', 'generation_config.json', 'tokenizer_config.json', 'tokenizer.json',
                 'special_tokens_map.json', 'added_tokens.json', 'vocab.json', 'merges.txt',
                 'model.safetensors.index.json', 'README.md']:
        url = f'https://huggingface.co/{MODEL}/resolve/{REV}/{name}'
        data = fetch(url, cache / name)
        if data.startswith(b'version https://git-lfs'):
            raise RuntimeError('Unresolved LFS pointer: ' + name)
        if name.endswith('.json'):
            json.loads(data)
        artifacts[name] = {'url': url, 'sha256': sha(data), 'bytes': len(data)}
    raw_url = f'https://media.githubusercontent.com/media/ucsb-mlsec/VulnLLM-R/{CODE}/{TRAIN_PATH}'
    raw = fetch(raw_url, ROOT / '.tools/vulnllmr-train/CWE-327.json')
    if len(raw) != 66640 or sha(raw) != TRAIN_SHA:
        raise RuntimeError('Training file does not match the audited Git LFS object')
    records = json.loads(raw)
    eligible = [x for x in records if not x.get('human') and len(x['code']) <= 5000]
    chosen, seen = [], set()
    for target in [0, 1]:
        subset = []
        for x in sorted(eligible, key=lambda x: str(x['idx'])):
            if x['target'] != target:
                continue
            digest = sha(x['code'].encode())
            if digest in seen:
                continue
            seen.add(digest)
            subset.append({'id': str(x['idx']), 'target': target, 'gold_cwes': x['CWE_ID'],
                           'code': x['code'], 'code_sha256': digest, 'dataset': x['dataset'],
                           'language': x['language'], 'training_eligible': False,
                           'role': 'development_smoke_only'})
            if len(subset) == 2:
                break
        if len(subset) != 2:
            raise RuntimeError('Cannot select two unique non-human records for each class')
        chosen.extend(subset)
    # Copy only literal prompt constants; never import or execute upstream code.
    prompt_url = f'https://raw.githubusercontent.com/ucsb-mlsec/VulnLLM-R/{CODE}/vulscan/utils/sys_prompts.py'
    prompt_bytes = fetch(prompt_url, ROOT / '.tools/vulnllmr-train/sys_prompts.py')
    constants = {}
    for node in ast.parse(prompt_bytes).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {'reasoning_user_prompt', 'our_cot'}:
                    constants[target.id] = ast.literal_eval(node.value)
    for item in chosen:
        # Fixed CWE scope for all examples; no sample-specific label, RELATED_CWE, or reason in prompt.
        item['prompt'] = constants['reasoning_user_prompt'].format(
            CODE=item['code'], CWE_INFO='Analyze only CWE-327: use of a broken or risky cryptographic algorithm.',
            REASONING=constants['our_cot'] + 'You should STRICTLY structure your response as follows:',
            ADDITIONAL_CONSTRAINT='')
    samples = {'scope': 'train-only engineering examples; not formal validation or benchmark evaluation',
               'source_commit': CODE, 'source_path': TRAIN_PATH, 'source_sha256': TRAIN_SHA,
               'excluded_human_records': sum(bool(x.get('human')) for x in records), 'samples': chosen}
    sample_path = ROOT / 'data/manifests/vulnllmr-development-smoke.json'
    sample_path.write_text(json.dumps(samples, ensure_ascii=False, indent=2) + '\n')
    index = json.loads((cache / 'model.safetensors.index.json').read_text())
    lock = {'model_id': MODEL, 'revision': REV, 'architecture': 'Qwen2ForCausalLM',
            'parameters': 7615616512, 'weight_bytes': index['metadata']['total_size'],
            'model_license': 'Apache-2.0 per model card', 'code_commit': CODE,
            'code_repository': 'https://github.com/ucsb-mlsec/VulnLLM-R', 'code_license': 'MIT',
            'metadata_artifacts': artifacts, 'prompt_source_sha256': sha(prompt_bytes),
            'sample_manifest': str(sample_path.relative_to(ROOT)),
            'sample_manifest_sha256': sha(sample_path.read_bytes()), 'formal_test_accessed': False,
            'reproduction_status': 'engineering preparation only; exact paper-to-checkpoint recipe unverified',
            'inference': {'seed': 42, 'do_sample': False, 'n': 1, 'max_input_tokens': 2048,
                          'max_new_tokens': 768, 'dtype': 'bf16 if supported, otherwise fp16',
                          'quantization': None, 'backend': 'transformers; not upstream vLLM'}}
    (ROOT / 'configs/vulnllmr.lock.json').write_text(json.dumps(lock, indent=2) + '\n')
    report = {'prepared_at': datetime.now(timezone.utc).isoformat(), 'metadata_bytes': sum(x['bytes'] for x in artifacts.values()),
              'full_weights_downloaded_locally': False, 'source_records': len(records),
              'excluded_human_records': samples['excluded_human_records'], 'selected_train_only_records': len(chosen),
              'formal_test_contents_accessed': False, 'code_commit': CODE,
              'training_source_sha256': TRAIN_SHA, 'sample_manifest_sha256': lock['sample_manifest_sha256']}
    (ROOT / 'docs/verification/vulnllmr-preparation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
