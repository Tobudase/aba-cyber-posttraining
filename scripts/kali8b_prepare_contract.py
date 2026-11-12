#!/usr/bin/env python3
"""Materialize an operator-frozen contract; never train, score or access DEV."""
import argparse,json
from pathlib import Path
def main():
 p=argparse.ArgumentParser();p.add_argument('--public-dir',type=Path,required=True);p.add_argument('--private-dir',type=Path,required=True);a=p.parse_args();public=a.public_dir.resolve();private=a.private_dir.resolve()
 assert public.name=='public' and private.name=='private' and public.parent==private.parent and public.is_dir() and private.is_dir()
 payload=json.loads((public/'setup_payload.json').read_text());assert set(payload)=={'readme','model_text','metrics_text','score_py','baseline_readme','baseline_source'}
 task=Path(__file__).resolve().parent
 for name in ['behavior_train_preview.jsonl','training_manifest.json','base_model.json','train_client.py']:
  target=task/name;assert target.is_file();dest=public/name
  if dest.is_symlink():assert dest.resolve()==target.resolve()
  else:assert not dest.exists();dest.symlink_to(target)
 assert not (public/'README.md').exists() and not (private/'score.py').exists(),'Do not overwrite an accepted grading contract'
 (public/'README.md').write_text(payload['readme']);(private/'score.py').write_text(payload['score_py'])
 base=private/'baseline_attempt';(base/'final_model').mkdir(parents=True,exist_ok=False)
 for name,text in [('final_model/model.json',payload['model_text']),('train_metrics.json',payload['metrics_text']),('README.md',payload['baseline_readme']),('run.py',payload['baseline_source'])]:(base/name).write_text(text)
 assert not (public/'README.md').is_symlink() and not (private/'score.py').is_symlink()
 print(json.dumps({'status':'CONTRACT_FILES_PREPARED_NOT_YET_NATIVE_VERIFIED','training_submissions':0,'DEV_rows':0,'next':'Submit native StructuredOutput(score,max);keep every verifier/reviewer enabled.'}))
if __name__=='__main__':main()
