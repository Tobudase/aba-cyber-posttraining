#!/usr/bin/env python3
"""Freeze one local fixed-SFT pilot before optimization; no model calls."""
from datetime import datetime, timezone
import json
from benchkit import ROOT, load_manifest, load_tokenizer, encode_supervision, sha, write_json


def main():
    target = ROOT / 'configs/kali-doc-sft-v1.protocol.json'
    if target.exists(): raise FileExistsError('Protocol already frozen; do not rewrite after outcomes')
    manifest = ROOT / 'data/benchkit/kali-doc-train-v1/manifest.json'
    _, rows = load_manifest(manifest, 'train'); tok = load_tokenizer('redsage')
    lengths = [len(encode_supervision(tok, r, 2048)['input_ids']) for r in rows]
    preparation = json.loads((ROOT / 'docs/verification/kali-doc-training-preparation-2026-10-22.json').read_text())
    if len(rows) != 108 or preparation['protected_operation_signature_overlap'] or preparation['reserved_confirmation_package_overlap']:
        raise ValueError('Data/boundary review is incomplete')
    checks = {'domain': ('data/benchkit/kali-domain-dev-v1/manifest.json', 'dev_search',
                        'docs/verification/kali-domain-e0-2026-10-22', 36),
              'retention': ('data/benchkit/kali-external-dev/manifest.json', 'dev_search',
                           'docs/verification/kali-prefix-ablation-2026-10-22/E0', 72)}
    evaluation = {}
    for name, (path, split, directory, count) in checks.items():
        receipt = ROOT / directory / 'receipt.json'
        if json.loads(receipt.read_text())['status'] != 'COMPLETE': raise ValueError('Baseline incomplete')
        evaluation[name] = {'manifest': path, 'manifest_sha256': sha((ROOT / path).read_bytes()), 'split': split,
            'rows': count, 'baseline_directory': directory, 'baseline_receipt_sha256': sha(receipt.read_bytes()),
            'baseline_predictions_sha256': sha((ROOT / directory / 'predictions.jsonl').read_bytes())}
    protocol = {'schema': 'kali.doc_sft.fixed_pilot.v1', 'frozen_at_utc': datetime.now(timezone.utc).isoformat(),
        'model_id': 'RISys-Lab/RedSage-K-SFT-GRPO', 'revision': '843e2e3096e7de68f5c35eb16238f4909f21695a',
        'conversion_receipt_sha256': sha((ROOT / 'docs/verification/kali-mlx-convert.json').read_bytes()),
        'train_manifest': str(manifest.relative_to(ROOT)), 'train_manifest_sha256': sha(manifest.read_bytes()),
        'train_rows': len(rows), 'source_review_sha256': sha((ROOT / 'docs/verification/kali-doc-training-preparation-2026-10-22.json').read_bytes()),
        'training': {'steps': len(rows), 'epochs': 1, 'batch_size': 1, 'learning_rate': 1e-5,
            'optimizer': 'AdamW', 'weight_decay': 0.0, 'seed': 42, 'shuffle_once': True,
            'lora': {'rank': 8, 'scale': 2.0, 'dropout': 0.0, 'keys': ['self_attn.q_proj', 'self_attn.v_proj']},
            'last_layers': 4, 'max_sequence_tokens': 2048, 'train_sequence_min': min(lengths), 'train_sequence_max': max(lengths),
            'supervision': 'native_full_chat_assistant_only_final_targets_no_help_context_no_fabricated_reasoning'},
        'inference': {'generation_prefix': 'sft-aligned', 'tool_help_context': False, 'temperature': 0,
                      'seed': 42, 'max_output_tokens': 1024, 'prefill_step_size': 256},
        'evaluation': evaluation, 'protected_files_sha256': preparation['protected_artifacts'],
        'budget': {'max_candidates': 1, 'train_deadline_seconds': 1800, 'eval_deadline_seconds': 1800,
                   'metal_memory_limit_bytes': 9 * 1024**3, 'metal_cache_limit_bytes': 256 * 1024**2},
        'decision_rule': 'Keep base unless domain nativeExact and strict option diagnostic both strictly improve, domain Total does not decrease, retention strict diagnostic does not decrease, and no truncation/runtime/XML failures.',
        'baseline_domain_correct': 6, 'baseline_retention_correct': 66,
        'confirmation_inference': False, 'official_test_enabled': False, 'ABA_executed': False,
        'limitations': ['Single fixed manualSFT engineering candidate; no actual ABA or formal benchmark score.',
            '108source-silver rows/55correlated intent families, assistant-reviewed, not expert gold or terminal-verified.',
            'Development already exposed to manual diagnostics; no independent generalization/significance claim.',
            'Quantized local model differs from official BF16/thinking protocol; no model/adapters published automatically.']}
    write_json(target, protocol)
    print(json.dumps({'frozen_protocol': str(target), 'sha256': sha(target.read_bytes()), 'rows': len(rows),
                      'steps': len(rows), 'max_sequence_tokens': max(lengths), 'learning_rate': 1e-5}, indent=2))


if __name__ == '__main__': main()
