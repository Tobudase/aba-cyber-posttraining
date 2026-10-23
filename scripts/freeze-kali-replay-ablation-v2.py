"""Freeze two equal-step training arms before either is generated/evaluated."""
from collections import defaultdict
import copy,json,hashlib,random
from datetime import datetime,timezone
from benchkit import ROOT,load_jsonl,write_json,write_jsonl,artifact_spec,sha,load_tokenizer,encode_supervision

def main():
 root=ROOT/'data/benchkit/kali-replay-ablation-v2'
 if root.exists():raise FileExistsError('Frozen experiment already exists; do not overwrite')
 check=json.loads((ROOT/'docs/verification/kali-replay-fixtures-2026-10-23.json').read_text())
 if check['status']!='PASS' or check['passed']!=32:raise ValueError('Replay semantic fixture verification required')
 domain=load_jsonl(ROOT/'data/benchkit/kali-doc-train-v2/train.jsonl');replay=load_jsonl(ROOT/'data/benchkit/kali-replay-v2/train.jsonl')
 groups=defaultdict(list)
 for r in domain:groups[r['template_family']].append(r)
 key=lambda r:sha(r['id'].encode())
 chosen=[sorted(rs,key=key)[0] for _,rs in sorted(groups.items())]
 chosen_ids={r['id'] for r in chosen}
 chosen+=sorted([r for r in domain if r['id'] not in chosen_ids],key=key)[:96-len(chosen)]
 assert len(chosen)==96 and len({r['id'] for r in chosen})==96
 common_order=list(chosen);random.Random(42).shuffle(common_order)
 extra=sorted(chosen,key=key)[:32]
 shared=json.loads((ROOT/'configs/kali-doc-sft-v1.protocol.json').read_text())
 native=load_tokenizer('redsage');manifest_hashes={};protocols={}
 for arm,addition in [('domain_control',extra),('domain_plus_replay',replay)]:
  # Same first 96 examples; matched positions for32extra steps, fixed shuffle of128slots.
  rows=[]
  for j,original in enumerate(common_order+addition):
   r=copy.deepcopy(original);r['source_training_id']=r['id'];r['id']=f'kali-v2-{arm}-{j:03d}';r['native_label']['custom_id']=r['id'];r['fixture']=r.get('fixture',None)
   rows.append(r)
  lengths=[len(encode_supervision(native,r,2048)['input_ids']) for r in rows]
  folder=root/arm;folder.mkdir(parents=True);write_jsonl(folder/'train.jsonl',rows)
  manifest={'schema':'benchkit.dataset.v1','benchmark':'kali','official_test':False,'splits':{'train':artifact_spec(folder/'train.jsonl',rows)},'arm':arm,'common_domain_rows':96,'extra_rows':32,'unique_source_training_rows':len({r['source_training_id'] for r in rows}),'selection':'One row per80domainfamilies plus16hash-selected second variants; control repeats32common rows; treatment adds32independent-utility rows. No result-driven selection.'}
  write_json(folder/'manifest.json',manifest)
  protocol=copy.deepcopy(shared);protocol.update(schema='kali.replay_ablation.v2',frozen_at_utc=datetime.now(timezone.utc).isoformat(),arm=arm,train_manifest=str((folder/'manifest.json').relative_to(ROOT)),train_manifest_sha256=sha((folder/'manifest.json').read_bytes()),train_rows=128)
  protocol['training'].update(steps=128,epochs=1,learning_rate=1e-5,train_sequence_min=min(lengths),train_sequence_max=max(lengths))
  protocol['source_review_sha256']=sha((ROOT/'docs/verification/kali-doc-training-v2-preparation-2026-10-23.json').read_bytes())
  protocol['runner_sha256']=sha((ROOT/'scripts/run-kali-replay-ablation-v2.py').read_bytes())
  protocol['budget']['max_candidates']=2
  protocol['limitations']=['Two predeclared arms/one seed; equal optimizer steps, not equal token/FLOP budget.','Control extra32domain presentations versus treatment32replay records: measures replacement under fixed-step budget, not pure added-data effect.','Development already exposed; no independent generalization or significance claim.','Source-silver; 32replayfixtures verified onLinux, domain labels not comprehensively execution-validated.','ManualMLX ablation; not actual ABA, GPU baseline, or official benchmark.']
  dest=ROOT/f'configs/kali-replay-v2-{arm}.protocol.json';write_json(dest,protocol);protocols[arm]=sha(dest.read_bytes())
 write_json(ROOT/'docs/verification/kali-replay-v2-freeze.json',{'status':'FROZEN_BEFORE_ARM_RUNS','frozen_at_utc':datetime.now(timezone.utc).isoformat(),'protocol_sha256':protocols,'domain_rows_available':len(domain),'common_domain_rows':96,'domain_families':len(groups),'replay_rows':32,'steps_per_arm':128,'max_candidates':2,'official_test_enabled':False,'confirmation_inference':False,'selection_rule':'Compare both to same original base under v1acceptance rule; do not promote any failing arm. No third candidate based on these outcomes.'})
 print(json.dumps(protocols))
if __name__=='__main__':main()
