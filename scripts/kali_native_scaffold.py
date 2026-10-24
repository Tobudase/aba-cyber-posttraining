"""Deterministic operator-provided setup, checked by unchanged native gates.

This is not an Agent tool or a protection-hook workaround. It writes only a new
owned run's empty output directories before any native Setup execution exists.
Input originals stay immutable. No labels/dev predictions, credential, score or
optimizer output is fabricated; baseline is explicitly a zero-step reference.
"""
import hashlib,json
from pathlib import Path

def digest(data):return hashlib.sha256(data).hexdigest()

def provision(run,task,payload):
 run=Path(run);task=Path(task)
 if (run/'workspace/search_1/setup_1').exists():raise ValueError('Setup already started; refuse runtime artifact injection')
 for folder in ['public','private']:
  if (run/folder).is_symlink() or any((run/folder).iterdir()):raise ValueError('New output directories must be empty and regular')
 manifest=json.loads((task/'manifest.json').read_text())
 if manifest['protocol_sha256']!=payload['protocol_sha256']:raise ValueError('Protocol mismatch')
 for name,h in manifest['files'].items():
  if Path(name).name!=name or digest((task/name).read_bytes())!=h:raise ValueError('Immutable task mismatch')
 for name in ['README.md','base_model.json','train_client.py','evaluate.py']:
  if digest(payload['files'][name].encode())!=manifest['files'][name]:raise ValueError('Operator input not frozen original')
 public=run/'public';private=run/'private'
 for name in ['README.md','base_model.json','train_client.py']:(public/name).write_text(payload['files'][name])
 (public/'train.jsonl').symlink_to(task/'train.jsonl')
 (private/'evaluate.py').write_text(payload['files']['evaluate.py'])
 (private/'score.py').write_text("import importlib.util\nfrom pathlib import Path\ndef score(output_dir):\n p=Path(__file__).with_name('evaluate.py');s=importlib.util.spec_from_file_location('frozen_evaluate',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m.evaluate(Path(output_dir)/'final_model')\n")
 base=private/'baseline_attempt';(base/'final_model').mkdir(parents=True)
 (base/'final_model/model.json').write_text(payload['files']['base_model.json'])
 (base/'run.py').write_text(payload['files']['train_client.py'])
 (base/'README.md').write_text('Original E0 model reference. No training. This is a zero-step baseline, not a candidate.\n')
 (base/'train_metrics.json').write_text(json.dumps({'optimizer_steps':0,'run_id':'E0','baseline':True,'protocol_sha256':payload['protocol_sha256']},indent=2)+'\n')
 report={'status':'OPERATOR_SCAFFOLD_PROVISIONED_BEFORE_NATIVE_SETUP','run_name':run.name,'protocol_sha256':payload['protocol_sha256'],'native_gates_unchanged':True,'task_hashes':manifest['files'],'operator_provided_not_agent_generated':True,'baseline_optimizer_steps':0,'official_test_rows':0,'confirmation_rows':0,'output_hashes':{str(p.relative_to(run)):digest(p.read_bytes()) for folder in [public,private] for p in folder.rglob('*') if p.is_file()}}
 (private/'operator-setup-provenance.json').write_text(json.dumps(report,indent=2)+'\n')
 return report
