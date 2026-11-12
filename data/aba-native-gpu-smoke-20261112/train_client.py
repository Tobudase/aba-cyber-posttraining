import hashlib,json,os,shutil,urllib.request
from pathlib import Path
def main():
 data=Path(os.environ['DATA_DIR']);out=Path(os.environ['OUTPUT_DIR'])
 body={'epochs':32,'learning_rate':0.1,'seed':42,'train_sha256':hashlib.sha256((data/'train.jsonl').read_bytes()).hexdigest(),'base_sha256':hashlib.sha256((data/'base_model.json').read_bytes()).hexdigest()}
 req=urllib.request.Request('http://127.0.0.1:29847/train',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=750) as r:result=json.load(r)
 assert result['status']=='NATIVE_GPU_CANDIDATE_PASS',result.get('error_type','Backend failed')
 assert result['model']['optimizer_steps']>0 and result['metrics']['device']=='cuda'
 out.mkdir(parents=True,exist_ok=True);(out/'final_model').mkdir(exist_ok=True)
 (out/'final_model/model.json').write_text(json.dumps(result['model'],sort_keys=True)+'\n')
 (out/'train_metrics.json').write_text(json.dumps(result['metrics'],sort_keys=True)+'\n')
 (out/'README.md').write_text('Synthetic eight-token model trained by bounded external CUDA backend; recipe 32 epochs, lr .1, seed42.\n')
 shutil.copyfile(__file__,out/'run.py')
 print(json.dumps({'backend':result['status'],'optimizer_steps':result['model']['optimizer_steps']}))
if __name__=='__main__':main()
