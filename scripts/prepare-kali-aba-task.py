#!/usr/bin/env python3
"""Prepare actual ABA task: public TRAIN, private host-side aggregate evaluation."""
import json,shutil
from pathlib import Path
from kali_cuda_jobs import ROOT,canonical,sha,frozen

p,inputs=frozen();phash=sha(canonical(p));root=ROOT/'.tools/kali-aba-cuda-task';root.mkdir(exist_ok=False)
(root/'train.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in inputs['train_rows']))
shutil.copyfile(ROOT/'scripts/kali_cuda_agent_client.py',root/'train_client.py')
(root/'base_model.json').write_text(json.dumps({'schema':'kali.cuda.pointer.v1','run_id':'E0','protocol_sha256':phash},indent=2)+'\n')
(root/'evaluate.py').write_text('''#!/usr/bin/env python3
"""Frozen private aggregate-only evaluator. Never train or alter this source."""
import argparse,json,urllib.request
from pathlib import Path
PROTOCOL_HASH='''+repr(phash)+'''
def evaluate(model_path):
 pointer=json.loads((Path(model_path)/'model.json').read_text())
 if pointer.get('schema')!='kali.cuda.pointer.v1' or pointer.get('protocol_sha256')!=PROTOCOL_HASH or pointer.get('run_id') not in ['E0','E2']:raise ValueError('Unapproved model reference')
 if pointer['run_id']=='E2' and (set(pointer)!={'schema','run_id','protocol_sha256','adapter_sha256'} or len(pointer['adapter_sha256'])!=64):raise ValueError('Missing real adapter reference')
 action='baseline_score' if pointer['run_id']=='E0' else 'candidate_score'
 req=urllib.request.Request('http://127.0.0.1:18742/v1/frozen',data=json.dumps({'action':action}).encode(),headers={'Content-Type':'application/json'},method='POST')
 with urllib.request.urlopen(req,timeout=2100) as r:result=json.load(r)
 if pointer['run_id']=='E2' and pointer['adapter_sha256']!=result['adapter_sha256']:raise ValueError('Pointer does not match evaluated persistent adapter')
 return {'score':float(result['score']),'components':result['components']}
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--model-path',required=True);args=a.parse_args();print(json.dumps(evaluate(args.model_path)))
''')
(root/'README.md').write_text('''# KaliBench real8B CUDA ABA controller/worker integration

Run ONE fixed-recipe candidate (no revisions) using train_client.py. This is an
engineering connection test with a real public8B learner and128 TRAIN records;
not an official benchmark, new data generation or autonomous tuning study.
The learner is RISys-Lab/RedSage-K-SFT-GRPO at pinned revision
843e2e3096e7de68f5c35eb16238f4909f21695a. CPU VM controls a remote finite
one-compatible-GPU Kubernetes worker via a loopback-only bridge. Do not install PyTorch,
download models, request GPUs locally, access kubeconfig or run containers here.
The remote worker applies NF4/BF16 and rank16/alpha32 q/v all-layer LoRA,
128 AdamW updates at1e-5, batch1, seed42, TRAIN-only supervision. No hyperparameter
changes are allowed in this check. train.jsonl exposes exact128 TRAIN rows;
client sends no rows or commands, host hashes and uses its frozen copy.

Setup: publish ONLY README.md, train.jsonl, train_client.py, base_model.json.
Keep evaluate.py PRIVATE, unchanged. There are no dev questions/labels on this VM.
Wrap evaluate.py in score.py with def score(output_dir): returning numeric score
and numeric components. Evaluate final_model/model.json. Use existing system
Python standard library; a normal Conda program environment is still required
by ABA. Never disable sandboxing, validation or score baseline gates.
Baseline: copy base_model.json to baseline/final_model/model.json; write
train_metrics.json with optimizer_steps=0, README.md identifying original base,
and copy train_client.py to baseline/run.py. Zero updates are legitimate for
baseline only. Frozen evaluator returns score0 for baseline; candidate score+1
only if ALL predeclared improvement/retention/format checks pass, else-1.
It returns only aggregate metrics, no dev questions, gold or raw predictions.

Designer: propose ONE direct execution of fixed train_client.py. references=[].
No search, ablations, retries, data synthesis, new dependencies or revisions.
Worker: copy public train_client.py into source_dir/run.py, then EXECUTE it using
OUTPUT_DIR=attempt_dir. The process blocks for real remote128-step training,
with a bounded scheduler wait and finite Job deadline; up to~10 minutes is
normal. Do not replace it with a stub or synthetic result. It writes:
final_model/model.json (real persistent adapter SHA reference),
train_metrics.json (real worker receipt), run.py (exact executed client), README.md.
Check positive128 optimizer steps and nonzero changed tensors. The actual
private safetensors adapter remains on persistent cluster storage; never
redistribute it. The pointer is the deployable reference for this engineering
bridge, not locally materialized model weights. Worker must not score directly.

Scoring can take up to~15 minutes for108 predeclared exposed development rows,
max256 greedy output tokens each, native prompt/scorer. No official test or
new confirmation rows are queried. Do not alter scoring or infer missing scores.
Finalizer: copy the selected existing four artifacts byte-for-byte into
deliverable, list all four relative_paths in StructuredOutput, then stop. If
baseline selected, retain baseline; never force promotion, invent updates,
retrain, reconstruct source or write a paper. Worker candidate may be rejected.
''')
files={x.name:sha(x.read_bytes()) for x in root.iterdir() if x.is_file()}
(root/'manifest.json').write_text(json.dumps({'protocol_sha256':phash,'files':files,'official_test_rows':0,'confirmation_rows':0},indent=2)+'\n')
print(json.dumps({'status':'PREPARED','protocol_sha256':phash,'task_files':list(files),'train_rows':128,'dev_rows_on_VM':0}))
