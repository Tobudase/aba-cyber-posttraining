"""Bounded replay-content comparison; exposed diagnostics only, no fresh confirmation."""
import gzip,json,sys,time
from kali_execution_jobs_20261114 import OUT,poll,cleanup,write
from kali_functional_gpu_execution_20261115 import collect,snapshot,data_for_job
from kali_functional_finalize_20261115 import gate,collect as collect_final,freeze_confirmation,confirmation_decision,export,finish
from kali_functional_decision_20261115 import decide
from kali_verified_recovery_analysis_20261115 import interim
from run_kali_rollout_repair_phase_20261115 import wait_marker
from run_kali_functional_behavior_phase_20261115 import run as behavior
def choose(name):
 d=OUT/name;v=decide(name,send=False);b=json.loads((d/'behavior-primary-summary.json').read_text());shift=json.loads((d/'behavior-shifted-summary.json').read_text());r=json.loads((d/'receipt.json').read_text());native=json.loads((d/'summary.json').read_text());tools=['hardlink','pyi-makespec','virtualenv','dnstwist'];eligible=[]
 for label,checks in v['checks'].items():
  z=shift[label];checks['exposed_shift64_atleast56_eachtool14']=z['shifted_dev64']['lower']>=56 and all(z['shifted_dev64:'+t]['lower']>=14 for t in tools);v['statistics'][label]['shifted_dev_PASS']=z['shifted_dev64']['lower']
  if all(checks.values()):eligible.append(label)
 def cost(label):
  arm=label.split('_step')[0];return sum(x['window_wall_seconds'] for x in r['traces'][arm])+sum(x['wall_seconds'] for x in r['rollout_audits'][arm])
 eligible.sort(key=lambda a:(-min([b[a]['new_dev32:'+t]['lower']/8 for t in tools]+[shift[a]['shifted_dev64:'+t]['lower']/16 for t in tools]),-shift[a]['shifted_dev64']['lower'],-b[a]['new_dev32']['lower'],-native[a]['old64']['native_points'],cost(a),a))
 v.update(eligible=eligible,action='verify' if eligible else 'stop',candidate=eligible[0] if eligible else None,reason='Fixed two96-update replay arms exhausted; exposed64 is development only, fresh64 still unqueried.');write(d/'primary-selection.json',v);return v
def run(name):
 d=OUT/name;assert not (d/'artifact.json').exists()
 wait_marker(name,'FUNCTIONAL_INFER R_step96 192/192');print('INTERIM '+json.dumps(interim(name,96)),flush=True);behavior('miw113-kali-cf-early-v13-1116',name,'early')
 wait_marker(name,'READY_FOR_FUNCTIONAL_DECISION');collect(name);r=json.loads((d/'receipt.json').read_text());write(d/'shifted-dev-predictions.json',r['shifted_dev_outputs'])
 write(d/'final-train-diagnostic-predictions.json',r['full_train_predictions'])
 # No confirmation/selection queries are authorized in this diagnostic phase.
 # Export and release the GPU before the final CPU-only scoring stages.
 gate(name,'/scratch/functional-decision.json',{'action':'stop','candidate':None,'reason':'Diagnostic training complete; export all candidates before offline CPU scoring.'})
 wait_marker(name,'READY_FOR_FUNCTIONAL_EXPORT',1800);collect_final(name,'robustness')
 print('EXPORT '+json.dumps(export(name)),flush=True)
 gate(name,'/scratch/functional-export-decision.json',{'action':'finish','reason':'All weights hash-verified; final functional scoring continues without a GPU.'})
 for _ in range(30):
  state=poll(name)
  if state['status'] in ['SUCCEEDED','FAILED']:
   cleanup(name)
   assert state['status']=='SUCCEEDED','Training/export did not finish successfully'
   break
  time.sleep(5)
 else:raise RuntimeError('Finish gate sent, no terminal observed')
 print('GPU_RELEASED_BEFORE_FINAL_CPU_SCORING',flush=True)
 behavior('miw113-kali-cf-fit-v13-1116',name,'finalfit');behavior('miw113-kali-cf-primary-v13-1116',name,'primary');behavior('miw113-kali-cf-shifted-v13-1116',name,'shifted')
 decision=choose(name);decision.update(action='stop',candidate=None,reason='Replay-content diagnosis only; no fresh confirmation or promotion');write(d/'primary-selection.json',decision)
 print('PRIMARY_DECISION '+json.dumps(decision),flush=True)
 print('PHASE_FINISHED '+json.dumps({'status':state['status'],'accepted':False}),flush=True)
if __name__=='__main__':run(sys.argv[1])
