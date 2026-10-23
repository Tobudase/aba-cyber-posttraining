"""Verify published CUDA evidence consistency; never repeat training or load tensors."""
import json
from benchkit import ROOT,sha,verify_sources

def main():
 verify_sources()
 base=ROOT/'docs/verification'
 evidence=json.loads((base/'kali-cuda-8b-smoke-2026-10-23.json').read_text());r=evidence['result']
 prefetch_path=base/'kali-cuda-prefetch-complete-2026-10-23.json';prefetch=json.loads(prefetch_path.read_text())
 lock=json.loads((ROOT/'configs/kali-cuda-prefetch.lock.json').read_text())
 if r['prefetch_receipt_sha256']!=sha(prefetch_path.read_bytes()):raise ValueError('Different prefetch receipt')
 if prefetch['files']!={x['name']:x['sha256'] for x in lock['files']}:raise ValueError('Pinned checkpoint mismatch')
 if evidence['source_sha256']!=sha((ROOT/'scripts/smoke-kali-cuda-8b.py').read_bytes()):raise ValueError('GPU runner changed')
 if r['status']!='PASS_REAL_8B_CUDA_TRAIN_SMOKE' or r['steps']!=20 or r['train_rows']!=2:raise ValueError('Incomplete smoke')
 if r['model_id']!=lock['model_id'] or r['revision']!=lock['revision']:raise ValueError('Different model')
 train=[json.loads(l) for l in (ROOT/'data/benchkit/kali-doc-train-v2/train.jsonl').read_text().splitlines()][:2]
 if r['train_ids']!=[x['id'] for x in train]:raise ValueError('Unexpected training rows')
 if any(r[k] for k in ['official_test_rows','confirmation_rows','development_rows','ABA_executed']):raise ValueError('Scope mismatch')
 config=json.loads((ROOT/'.tools/benchkit/models/redsage/config.json').read_text())
 hidden=config['hidden_size'];head=config.get('head_dim',hidden//config['num_attention_heads'])
 qout=config['num_attention_heads']*head;vout=config['num_key_value_heads']*head;layers=config['num_hidden_layers']
 expected=layers*16*(hidden+qout+hidden+vout)
 if r['trainable_parameters']!=expected or r['changed_parameter_tensors']!=layers*4:raise ValueError('LoRA architecture count mismatch')
 if len(r['losses'])!=20 or r['reload_max_logit_delta']>1e-4:raise ValueError('Persistence check mismatch')
 cleanup=json.loads((base/'kali-resource-cleanup-2026-10-23.json').read_text())
 if cleanup['own_kali_pods_remaining'] or cleanup['GPU_allocation_held_after_completion']:raise ValueError('Cleanup incomplete')
 print(json.dumps({'status':'PASS_PUBLIC_GPU_RECEIPT_CONSISTENCY','model':r['model_id'],'GPU':r['gpu'],'recorded_steps':20,'LoRA_parameter_count_matches_architecture':expected,'adapter_reload_delta':r['reload_max_logit_delta'],'new_model_calls':0,'scope':'Published receipt/source/architecture consistency; private tensors and actual training execution are not independently re-run'},indent=2))
if __name__=='__main__':main()
