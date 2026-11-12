"""Build an immutable, bounded native ABA task after fixed controls are scored."""
import gzip,hashlib,json,subprocess,sys
from pathlib import Path
from kali8b_native_bridge import freeze_baseline
ROOT=Path(__file__).resolve().parents[1];S=ROOT/'data/benchkit/kali-8b-verified64-study-2026-11-12'
def build(out):
 out=Path(out);task=out/'task';task.mkdir();baseline=freeze_baseline()
 payload=json.loads(gzip.decompress((S/'P13/payload-private.json.gz').read_bytes()))
 encoded=out/'training-encoded-host-private.json';encoded.write_text(json.dumps(payload['train_rows'],separators=(',',':'))+'\n')
 silver=ROOT/'data/benchkit/kali-fixture-train-v2-2026-11-12/train.jsonl'
 all_silver=list(map(json.loads,silver.read_text().splitlines()));preview_rows=[]
 for tool in ['hardlink','virtualenv','dnstwist','pyi-makespec']:
  group=[r for r in all_silver if r['id'].startswith('kali-fixture-'+tool+'-')];assert len(group)>=2;preview_rows.extend([group[0],group[-1]])
 preview=[{'id':r['id'],'group_id':r['group_id'],'question':next(m['content'] for m in r['messages'] if m['role']=='user'),'target':r['target'],'quality':r['quality'],'preview_projection_only':True} for r in preview_rows]
 (task/'behavior_train_preview.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in preview))
 manifest={'status':'FROZEN_NATIVE_ABA_TWO_RECIPES','model_id':baseline['pointer']['model_id'],'model_revision':baseline['pointer']['model_revision'],'training_rows':733,'quality_counts':{'publisher_verified':669,'behavior_verified_silver':64},'optimizer_steps':733,'supervised_tokens':17439,'train_encoded_sha256':hashlib.sha256(encoded.read_bytes()).hexdigest(),'full_TRAIN_access':'train_client.py export-train writes the733 exact masked TRAIN rows under OUTPUT_DIR;compressed hash-checked transfer;no DEV labels','recipes':{c:json.loads((S/c/'protocol-private.json').read_text())['optimizer'] for c in ['P13','P14']},'protocol_sha256':json.loads((S/'protocol-freeze-private.json').read_text())['protocol_sha256'],'official_TEST_rows':0,'final64_used':False}
 (task/'training_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 (task/'base_model.json').write_text(json.dumps(baseline['pointer'],indent=2)+'\n')
 (task/'baseline_metrics.json').write_text(json.dumps({'baseline':True,'optimizer_steps':baseline['pointer']['optimizer_steps'],'source':'completed fixed-control GPU receipt or original E0','official_TEST_rows':0},indent=2)+'\n')
 (task/'train_client.py').write_bytes((ROOT/'scripts/kali8b_native_client.py').read_bytes())
 (task/'README.md').write_text('''# KaliBench verified64: bounded native ABA adaptation
The 8B base is RISys-Lab/RedSage-K-SFT-GRPO at the immutable revision in training_manifest.json. This is an internal TRAIN-derived DEV study, not an official TEST score. The host owns frozen data, recipes, GPU jobs, and grader. No judge examples or cluster credentials are supplied. Training uses733 masked tokenized TRAIN rows:669 publisher-verified and64 locally behavior-verified silver rows (32 correlated families). Silver is not independent expert gold. Public behavior_train_preview.jsonl projects8 representative new authored rows (two per tool), showing their questions, targets and quality tier; this is a small readable preview, not the training payload. To inspect all733 exact encoded rows, use train_client.py export-train with DATA_DIR=PUBLIC and OUTPUT_DIR=your scratch/artifact directory; the host transfers only TRAIN with compression and verifies its manifest SHA. This avoids copying a megabyte single-line JSON through truncated Read/Write output. Export is CPU-only, never a training submission.

The baseline pointer is the best gate-passing fixed control (or E0 if neither passes). It is an actual saved model, not a synthetic zero score. Each ABA candidate starts again from the ORIGINAL 8B weights, not from this champion. The two preregistered alternatives are P13 (mixed data, lr1e-5, seed43) and P14 (mixed data, lr2e-5, seed42), 733 genuine optimizer updates each, one GPU at a time. All other optimizer/inference settings are frozen. Do not invent additional candidates or revisions. requested_gpus=0 for the CPU Worker: the trusted client dispatches an external ordinary-priority GPU job. Search budget two is not equal to fixed SFT's one-candidate search budget.

Setup must use prepare_contract.py as described in setup_scaffold.md. It prepares the plain public README, private score module and actual baseline. Native verification/review MUST still run. Only approved TRAIN material and the answer-free helper/setup_payload.json may be public. Do not copy protected task files with cp or shutil, improvise a grader, train or submit during Setup/Designer. Use supported read-only public symlinks for approved task inputs. No DEV labels occur in the helper or payload.

Designer: propose two DISTINCT plans, one for each of P13/P14, no revisions or external references. Worker: read training_manifest.json and the unmodified train_client.py. In a Bash command set DATA_DIR=PUBLIC, OUTPUT_DIR=your artifacts/full; call python train_client.py submit --candidate P13 (or P14 as assigned). Submission returns quickly. GPU queue/training can take up to 3 hours. Poll the same client's wait action about once per minute; sleep55 and client wait may be grouped in a Bash timeout100000. IN_PROGRESS is normal, never submit a duplicate or claim completion. On REAL_GPU_TRAINING_COMPLETE call finalize with the same candidate. This writes final_model/model.json, train_metrics.json, run.py, README.md. Inspect all four and submit only after real updates and verified adapter recovery. Host failures must be reported, never replaced by invented metrics. The host denies training unless native Setup passed and a Worker is active. Do not access judge files or alter the client/data.

PRIVATE score is the frozen host internal DEV score: 100*(candidate native mean minus E0) if all predeclared retention/gain gates pass, otherwise -1. Baseline is measured by the same host. Larger is better. Worker cannot score or read private DEV; native Score does this after submission. Finalizer copies all four selected files byte-for-byte into deliverable; do not retrain or reconstruct. Pointers reference actual private adapters, whose tensors are recovered, SHA verified and retained by the host; no tensors need copying to this CPU VM. Final sealed64 confirmation happens only after the native search finishes and selection is frozen.
''')
 (task/'evaluate.py').write_text('''import argparse,json,urllib.request
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--model-path',type=Path,required=True);a=p.parse_args();pointer=json.loads((a.model_path/'model.json').read_text())
r=urllib.request.Request('http://127.0.0.1:29847/candidate',data=json.dumps({'action':'score','pointer':pointer}).encode(),headers={'Content-Type':'application/json'})
with urllib.request.urlopen(r,timeout=100) as s:result=json.load(s)
assert 'score' in result and not result.get('status')=='FAILED'
print(json.dumps(result))
''')
 score_source='''import json,urllib.request
from pathlib import Path
def score(output_dir):
 pointer=json.loads((Path(output_dir)/'final_model/model.json').read_text())
 request=urllib.request.Request('http://127.0.0.1:29847/candidate',data=json.dumps({'action':'score','pointer':pointer}).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(request,timeout=100) as response:result=json.load(response)
 assert 'score' in result and result.get('status')!='FAILED'
 return result
'''
 model_text=(task/'base_model.json').read_text();metrics_text=(task/'baseline_metrics.json').read_text();baseline_readme='Existing measured frozen baseline;not a new ABA training candidate.\n'
 baseline_source="import os,pathlib\nMODEL="+repr(model_text)+"\nMETRICS="+repr(metrics_text)+"\nREADME="+repr(baseline_readme)+"\nout=pathlib.Path(os.environ['OUTPUT_DIR']);(out/'final_model').mkdir(parents=True,exist_ok=True);(out/'final_model/model.json').write_text(MODEL);(out/'train_metrics.json').write_text(METRICS);(out/'README.md').write_text(README);source=pathlib.Path(__file__).read_bytes();(out/'run.py').write_bytes(source)\n"
 contract=(task/'README.md').read_text()+'\n## Frozen scoring contract\nMetric:score. Direction:max. Judge is the trusted host-certified external scorer;baseline and candidates use the same private score(output_dir) callable. No DEV labels are exposed.\n'
 setup_payload={'readme':contract,'model_text':model_text,'metrics_text':metrics_text,'score_py':score_source,'baseline_readme':baseline_readme,'baseline_source':baseline_source}
 (task/'setup_payload.json').write_text(json.dumps(setup_payload,indent=2)+'\n');(task/'prepare_contract.py').write_bytes((ROOT/'scripts/kali8b_prepare_contract.py').read_bytes())
 (task/'setup_scaffold.md').write_text('''# Execute the frozen helper, then native verification
Read this file first. This is a prepared benchmark contract,not from-scratch grader design. Keep every native verifier/reviewer. No training/submissions.
Using Bash, create ONLY TWO read-only symlinks with ln -s: PUBLIC/prepare_contract.py to TASK/prepare_contract.py,and PUBLIC/setup_payload.json to TASK/setup_payload.json. These supported task-to-public links contain no DEV labels. Do not use cp,mv,shutil or heredocs to copy protected task files.
Execute python PUBLIC/prepare_contract.py --public-dir PUBLIC --private-dir PRIVATE. It writes plain PUBLIC/README.md,PRIVATE/score.py and four actual baseline files from frozen answer-free constants,and links the four approved inputs. It neither scores nor submits nor trains. Do not append/rewrite its outputs,read every TRAIN row,inspect logging modules,or log a zero-step baseline.
Then immediately submit StructuredOutput(metric_name="score",metric_direction="max"). The native deterministic baseline verifier and semantic reviewer must run normally. Fix a concrete verifier error;never replace its result. All true DEV labels stay host-only. The baseline is the already measured E0/fixed model,not a new training candidate.
''')
 tmp=out/'config-template.json';subprocess.run([sys.executable,str(ROOT/'scripts/build-aba-synthetic-config.py'),'--remote-root','/mnt/aba-scratch/study','--output',str(tmp)],capture_output=True,check=True)
 config=json.loads(tmp.read_text());tmp.unlink();config['run']['task_name']='kali8b-verified64';config['run']['budget'].update(wall_clock_minutes=360,cost_usd=30,per_agent_cost_cap_usd=12)
 config['llm']['default']['model']='qwen3';config['llm']['retry_ceiling_s']=45
 config['llm']['system_instructions'].update(setup='FIRST Read setup_scaffold.md. Symlink ONLY prepare_contract.py and setup_payload.json from TASK into PUBLIC with ln -s,execute the helper with --public-dir and --private-dir,then immediately StructuredOutput(score,max). No cp/shutil on protected data,large file transcription,appended contract,TRAIN inspection,logging-module inspection,training,or grader invention. The helper only materializes the supplied contract. All native verification/review MUST run. Keep evaluate.py/baseline_metrics.json private;helper/payload contain no labels and are approved public inputs.',designer='Read README.md and training_manifest.json. Propose exactly two DISTINCT plans: P13 lr1e-5 seed43 and P14 lr2e-5 seed42, both733updates. requested_gpus=0 because external broker dispatches GPU. No revisions, no extra recipes, references=[]. Do not submit or train.',worker='Use unmodified public/train_client.py for the assigned P13 or P14. Submit once, poll wait every55s with Bash timeout100000, until REAL_GPU_TRAINING_COMPLETE, then finalize and inspect all four files. IN_PROGRESS is normal for up to3hours; do not resubmit. Never fabricate, implement another trainer, or read judge material. Explicitly include --candidate in every call. DATA_DIR is PUBLIC, OUTPUT_DIR is artifacts/full.',finalizer='Copy selected final_model/model.json,train_metrics.json,README.md,run.py preserving bytes into deliverable and immediately submit StructuredOutput. Do not retrain, rewrite, score again, or invent missing files.')
 config['search']['input'].update(parallel=1,num_designs=2,num_revisions=1,max_evaluations=2,early_stopping=2)
 for unit in config['work_units']:
  if unit['name']=='worker':unit['budget']['minutes']=200
  elif unit['name']=='setup':unit['budget']['minutes']=45
  elif unit['name']=='setup_review':unit['budget']['minutes']=15
  elif unit['name']=='designer':unit['budget']['minutes']=20
  elif unit['name'] in ['designer_review','worker_review']:unit['budget']['minutes']=10
  elif unit['name']=='finalizer':unit['budget']['minutes']=20
  elif unit['name']=='score_program':unit['budget']['minutes']=5
  elif unit['name']=='training':unit['budget']['minutes']=195
 (out/'config.json').write_text(json.dumps(config,indent=2)+'\n')
 runtime_files=['run-kali8b-native-study-20261112.py','build-kali8b-native-study.py','build_kali8b_native_study_import.py','build-aba-synthetic-config.py','nrp_anthropic_transport.py','kali8b_native_bridge.py','kali8b_native_mailbox.py','kali8b_native_client.py','kali8b_native_vm.py','kali8b_native_journal.py','kali8b_native_install.sh','kali8b_study_jobs.py','kali8b_prepare_contract.py']
 frozen={'task_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in task.iterdir()},'runtime_source_sha256':{n:hashlib.sha256((ROOT/'scripts'/n).read_bytes()).hexdigest() for n in runtime_files},'config_sha256':hashlib.sha256((out/'config.json').read_bytes()).hexdigest(),'baseline':baseline,'native_candidates_maximum':2,'official_TEST_rows':0,'final64_used':False}
 (out/'native-task-freeze-private.json').write_text(json.dumps(frozen,indent=2)+'\n');return config
