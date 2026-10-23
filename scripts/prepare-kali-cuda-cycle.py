#!/usr/bin/env python3
"""Freeze a separate CUDA engineering study; never load confirmation bodies."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
from benchkit import ROOT,load_manifest,load_jsonl,write_json

def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def sha(x):return hashlib.sha256(x).hexdigest()
def prepare():
 out=ROOT/'configs/kali-cuda-cycle-v1.protocol.json'
 if out.exists():raise SystemExit('Frozen protocol already exists; refusing overwrite')
 old=json.loads((ROOT/'configs/kali-replay-v2-domain_plus_replay.protocol.json').read_text())
 manifest=ROOT/old['train_manifest'];_,train=load_manifest(manifest,'train')
 projections=[];evaluation={}
 for name,v in old['evaluation'].items():
  m=ROOT/v['manifest'];spec=json.loads(m.read_text());part=spec['splits']['dev_search'];f=m.parent/part['file']
  assert sha(f.read_bytes())==part['sha256'];rows=load_jsonl(f)
  previous=load_jsonl(ROOT/v['baseline_directory']/'predictions.jsonl');indexed={x['id']:x for x in previous}
  assert len(rows)==v['rows'] and len({r['id'] for r in rows})==len(rows)
  projections += [{'id':r['id'],'messages':r['messages'],'prompt_sha256':indexed[r['id']]['prompt_sha256'],'set':name} for r in rows]
  evaluation[name]={'manifest':v['manifest'],'manifest_sha256':sha(m.read_bytes()),'split':'dev_search','file_sha256':sha(f.read_bytes()),'rows':len(rows)}
 lock=json.loads((ROOT/'configs/kali-cuda-prefetch.lock.json').read_text());archive=json.loads((ROOT/'docs/verification/kali-cuda-runtime-archive.json').read_text())
 p={'schema':'kali.cuda_cycle.v1','frozen_at_utc':datetime.now(timezone.utc).isoformat(),'model_id':lock['model_id'],'revision':lock['revision'],
    'checkpoint_files':{r['name']:r['sha256'] for r in lock['files']},'runtime_archive_sha256':archive['sha256'],
    'runner_sha256':sha((ROOT/'scripts/run-kali-cuda-cycle.py').read_bytes()),'GPU_model':'NVIDIA A10',
    'image':json.loads((ROOT/'configs/gpu-runtime-image.lock.json').read_text())['image'],
    'train_manifest':str(manifest.relative_to(ROOT)),'train_manifest_sha256':sha(manifest.read_bytes()),'train_rows_sha256':sha(canonical(train)),
    'inference_rows_sha256':sha(canonical(projections)),
    'training':{'steps':128,'epochs':1,'batch_size':1,'learning_rate':1e-5,'seed':42,'optimizer':'AdamW','weight_decay':0,'lora_rank':16,'lora_alpha':32,'lora_targets':['q_proj','v_proj'],'all_layers':True,'max_sequence_tokens':2048},
    'inference':{'generation_prefix':'sft-aligned','tool_help_context':False,'temperature':0,'seed':42,'max_output_tokens':256},
    'evaluation':evaluation,'official_test_enabled':False,'confirmation_enabled':False,
    'budget':{'max_manual_candidates':1,'max_ABA_candidates':1,'parallel_GPUs':1,'job_deadline_seconds':1800,'scheduler_wait_seconds':360},
    'decision_rule':'Keep base unless native domain exact and strict option diagnostic both strictly improve, domain total does not decrease, retention strict does not decrease, and no truncation/runtime/XML failures.',
    'limitations':['Engineering diagnostic, one seed, already exposed development sets; no generalization or official ranking claim.',
      'CUDA NF4, all-layer rank16 and max256 differ from Mac MLX rank8 last4 layers max1024; do not compare scores as paired reproduction.',
      'E1 manual and E2 ABA use identical frozen recipe for controller/worker parity only; no adaptive data generation or hyperparameter search in this integration.',
      'Source-silver labels; model already trained official TRAIN. New confirmation and official test remain unqueried.',
      'GPU utilization samples begin after staging; report staging and whole Job allocation separately.']}
 projection=ROOT/'data/benchkit/kali-cuda-cycle-v1/inference-inputs.json';write_json(projection,projections)
 write_json(out,p)
 private=ROOT/'.tools/kali-cuda-cycle-v1-inputs.json';write_json(private,{'train_rows':train,'inference_rows':projections})
 print(json.dumps({'status':'FROZEN','protocol_sha256':sha(canonical(p)),'train':len(train),'inference':len(projections)}))
if __name__=='__main__':prepare()
