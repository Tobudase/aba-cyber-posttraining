#!/usr/bin/env python3
"""Recompute the published synthetic result and check source/deliverable hashes."""
import hashlib,importlib.util,json,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];D=ROOT/'results/aba-native-gpu-smoke-2026-11-12';TASK=ROOT/'data/aba-native-gpu-smoke-20261112'
def main():
 s=json.loads((D/'verified-summary.json').read_text());assert s['status']=='NATIVE_ABA_GPU_PIPELINE_VERIFIED' and s['native_result']=='completed'
 assert s['native_worker_trigger_verified_before_GPU'] and s['optimizer_steps']==256
 for name,h in s['frozen_task_file_sha256'].items():assert hashlib.sha256((TASK/name).read_bytes()).hexdigest()==h,name
 for name,h in s['four_delivered_file_sha256'].items():assert hashlib.sha256((D/'deliverable'/name).read_bytes()).hexdigest()==h,name
 assert s['gpu_request']['train_sha256']==s['frozen_task_file_sha256']['train.jsonl']
 assert s['gpu_request']['base_sha256']==s['frozen_task_file_sha256']['base_model.json']
 spec=importlib.util.spec_from_file_location('frozen_evaluator',TASK/'evaluate.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 actual=m.evaluate(D/'deliverable/final_model')
 for k,v in s['selected_local_score'].items():assert abs(actual[k]-v)<1e-9,(k,actual[k],v)
 with tempfile.TemporaryDirectory() as d:
  p=Path(d);(p/'model.json').write_bytes((TASK/'base_model.json').read_bytes());base=m.evaluate(p)
 for k,v in s['baseline_local_score'].items():assert abs(base[k]-v)<1e-9
 assert s['training']['reload_max_abs_diff']==0 and s['gpu_cleanup_errors']==s['controller_cleanup_errors']==0
 assert s['artifact_64MiB_roundtrip_sha256_match'] and s['task_hashes_unchanged']
 print(json.dumps({'status':'PUBLISHED_SYNTHETIC_RESULT_VERIFIED','optimizer_steps':actual['optimizer_steps'],'baseline_dev_nll':base['dev_nll'],'selected_dev_nll':actual['dev_nll'],'scope':'Eight-token runtime smoke; no 8B LLM training or official benchmark result.'}))
if __name__=='__main__':main()
