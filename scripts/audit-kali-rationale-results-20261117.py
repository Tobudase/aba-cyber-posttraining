"""Audit complete fixed-run evidence and produce aggregate paired diagnostics."""
import argparse,collections,hashlib,importlib.util,json,math,re,statistics,sys
from pathlib import Path
from benchkit import strict_option_values
def exact_p(g,l):
 n=g+l
 return min(1.,2*sum(math.comb(n,k) for k in range(min(g,l)+1))/2**n) if n else 1.
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--stage',type=Path,required=True);parser.add_argument('--run',type=Path,required=True);parser.add_argument('--worker-log',type=Path,required=True);parser.add_argument('--scorer',type=Path,required=True);args=parser.parse_args();STAGE=args.stage;RUN=args.run
 data=json.loads((STAGE/'paired-training-private.json').read_text());compare=json.loads((RUN/'comparison-private.json').read_text());receipt=json.loads((RUN/'execution-receipt.json').read_text())
 assert receipt['status']=='COMPLETE' and receipt['returncode']==0
 assert receipt['packages']==data['model_protocol']['expected_packages']
 assert receipt['nonthinking_control_returncode']==0
 assert 'FIXED_PAIR_COMPLETE' in args.worker_log.read_text()
 refs=json.loads((STAGE/'evaluation-references-private.json').read_text());inp=json.loads((STAGE/'evaluation-inputs-private.json').read_text());ids=[r['id'] for r in inp]
 ep=json.loads((STAGE/'evaluation-protocol.json').read_text());mp=data['model_protocol'];expected=hashlib.sha256((STAGE/'paired-training-private.json').read_bytes()).hexdigest()
 pred={};receipts={};train={};diagnostic={};changed={};paired={}
 for arm in ['answer_only','reasoning']:
  rec=json.loads((RUN/arm/'receipt.json').read_text());trace=json.loads((RUN/arm/'trace.json').read_text());receipts[arm]=rec
  assert rec['updates']==len(trace)==48 and rec['data_sha256']==expected and rec['model_revision']==mp['model_revision']
  wanted=[[data['encoded'][arm][i]['id'] for i in order[j:j+4]] for order in data['epoch_orders'] for j in range(0,48,4)]
  assert [r['ids'] for r in trace]==wanted
  assert all(math.isfinite(r[k]) and r[k]>0 for r in trace for k in ['loss','gradient_norm','command_loss_monitor'])
  assert rec['training_target_tokens']==sum(r['target_tokens'] for r in trace)==4*sum(r['target_tokens'] for r in data['encoded'][arm])
  train[arm]={'updates':48,'epochs':4,'seconds':rec['seconds'],'supervised_tokens':rec['training_target_tokens'],'epoch_mean_loss':[statistics.mean(t['loss'] for t in trace if t['epoch']==e) for e in range(1,5)],'epoch_mean_command_loss':[statistics.mean(t['command_loss_monitor'] for t in trace if t['epoch']==e) for e in range(1,5)],'gradients_finite_nonzero':True}
 assert receipts['answer_only']['initial_adapter_sha256']==receipts['reasoning']['initial_adapter_sha256']
 adapter_checks={}
 for arm in ['answer_only','reasoning']:
  aa=json.loads((RUN.parent/(arm+'-adapter-audit-private.json')).read_text());assert aa['adapter_sha256']==receipts[arm]['adapter_sha256'] and aa['all_finite'] and aa['all_72_B_matrices_nonzero'] and aa['receipt_hash_matches']
  adapter_checks[arm]={k:v for k,v in aa.items() if k!='adapter_sha256'}
 for arm in ['base','answer_only','reasoning']:
  x=json.loads((RUN/(arm+'-predictions.json')).read_text());assert x['status']=='COMPLETE' and [r['id'] for r in x['predictions']]==ids and x['model_revision']==mp['model_revision']
  assert x['adapter_sha256']==(None if arm=='base' else receipts[arm]['adapter_sha256'])
  pred[arm]=x['predictions'];diagnostic[arm]={}
  for panel in ['development24','old64']:
   rr=[r for r in pred[arm] if r['panel']==panel];ss=[r for r in compare['details'][arm] if r['panel']==panel]
   diagnostic[arm][panel]={'closed_think':sum('</think>' in r['response'] for r in rr),'empty_think':sum(bool(re.search(r'<think>\s*</think>',r['response'])) for r in rr),'mean_generated_tokens':statistics.mean(r['generated_tokens'] for r in rr),'median_generated_tokens':statistics.median(r['generated_tokens'] for r in rr),'valid_but_strict_wrong':sum(not s['invalid'] and not s['strict'] for s in ss),'no_closed_think':sum('</think>' not in r['response'] for r in rr)}
  diagnostic[arm]['evaluation_seconds']=x['seconds']
 for old,new in [('base','answer_only'),('base','reasoning'),('answer_only','reasoning')]:
  key=old+'_to_'+new;paired[key]={};changed[key]=[]
  for panel in ['development24','old64']:
   aa=[r for r in compare['details'][old] if r['panel']==panel];bb=[r for r in compare['details'][new] if r['panel']==panel]
   counts=collections.Counter(('both_correct' if a['strict'] and b['strict'] else 'gain' if b['strict'] else 'loss' if a['strict'] else 'both_wrong') for a,b in zip(aa,bb))
   g,l=counts['gain'],counts['loss'];paired[key][panel]={**dict(counts),'gain':g,'loss':l,'net':g-l,'paired_exact_p_two_sided':exact_p(g,l)}
   paired[key][panel]['gain_from_truncated']=sum(not a['strict'] and b['strict'] and a['truncated'] for a,b in zip(aa,bb))
   paired[key][panel]['gain_from_other_invalid']=sum(not a['strict'] and b['strict'] and a['invalid'] and not a['truncated'] for a,b in zip(aa,bb))
   paired[key][panel]['gain_from_valid_wrong']=sum(not a['strict'] and b['strict'] and not a['invalid'] for a,b in zip(aa,bb))
   paired[key][panel]['loss_to_truncated']=sum(a['strict'] and not b['strict'] and b['truncated'] for a,b in zip(aa,bb))
   paired[key][panel]['loss_to_other_invalid']=sum(a['strict'] and not b['strict'] and b['invalid'] and not b['truncated'] for a,b in zip(aa,bb))
   paired[key][panel]['loss_to_valid_wrong']=sum(a['strict'] and not b['strict'] and not b['invalid'] for a,b in zip(aa,bb))
   for a,b in zip(aa,bb):
    if a['strict']!=b['strict']:changed[key].append({'id':a['id'],'panel':panel,'tool':refs[a['id']]['tool_name'],'direction':'gain' if b['strict'] else 'loss','before_invalid':a['invalid'],'after_invalid':b['invalid'],'before_truncated':a['truncated'],'after_truncated':b['truncated']})
 # Independently re-read predictions and reproduce frozen scoring, including the extra prompt-mode control.
 scorer=args.scorer;assert hashlib.sha256(scorer.read_bytes()).hexdigest()==ep['scorer_sha256']
 spec=importlib.util.spec_from_file_location('native_score_audit',scorer);sc=importlib.util.module_from_spec(spec);spec.loader.exec_module(sc)
 control=json.loads((RUN/'base-nonthinking-predictions.json').read_text());assert control['status']=='COMPLETE' and control['adapter_sha256'] is None and control['model_revision']==mp['model_revision'] and [r['id'] for r in control['predictions']]==ids
 rescored={};components={}
 for arm,rr in {**pred,'base_nonthinking':control['predictions']}.items():
  ss=[];component_rows=[]
  for r in rr:
   text=r['content'];parts=re.findall(r'<output>\s*([\s\S]*?)\s*</output>',text)
   valid=bool(r['finish_reason']=='stop' and len(parts)==1 and text.count('<output>')==text.count('</output>')==1 and parts[0].strip())
   final='<output>'+parts[0].strip()+'</output>' if valid else ''
   native=sc.score_one(refs[r['id']],final);component_rows.append({'panel':r['panel'],**{k:native[k] if valid else 0. for k in ['tool_score','optional_f1','positional_f1']}})
   ss.append({'id':r['id'],'panel':r['panel'],'strict':bool(valid and strict_option_values(refs[r['id']],final,sc)),'partial':sc.score_one(refs[r['id']],final)['total_score'] if valid else 0.,'invalid':not valid,'truncated':r['finish_reason']=='length','tokens':r['generated_tokens']})
  components[arm]={panel:{k:statistics.mean(x[k] for x in component_rows if x['panel']==panel) for k in ['tool_score','optional_f1','positional_f1']} for panel in ['development24','old64']}
  rescored[arm]=ss
  if arm!='base_nonthinking':assert ss==compare['details'][arm]
 control_summary={panel:{'n':len(rr),'strict':sum(x['strict'] for x in rr),'native_partial':statistics.mean(x['partial'] for x in rr),'invalid':sum(x['invalid'] for x in rr),'truncated':sum(x['truncated'] for x in rr),'tokens':sum(x['tokens'] for x in rr)} for panel in ['development24','old64'] if (rr:=[x for x in rescored['base_nonthinking'] if x['panel']==panel])}
 control_paired={}
 for arm in ['base','answer_only','reasoning']:
  control_paired[arm]={}
  for panel in ['development24','old64']:
   pairs=[(a,b) for a,b in zip(rescored['base_nonthinking'],rescored[arm]) if a['panel']==panel]
   g=sum(not a['strict'] and b['strict'] for a,b in pairs);l=sum(a['strict'] and not b['strict'] for a,b in pairs)
   control_paired[arm][panel]={'gain_over_nonthinking':g,'loss_vs_nonthinking':l,'net':g-l,'paired_exact_p_two_sided':exact_p(g,l)}
 control_correct={r['id'] for r in rescored['base_nonthinking'] if r['panel']=='old64' and r['strict']};control_retention={}
 for arm in ['answer_only','reasoning']:
  kept=sum(r['id'] in control_correct and r['strict'] for r in rescored[arm]);control_retention[arm]={'kept':kept,'base_nonthinking_correct':len(control_correct),'rate':kept/len(control_correct) if control_correct else None}
 train_tools={'llvm-readelf','pepack','pescan','readpe','llvm-nm'};coverage={};by_tool_overlap={}
 for arm in pred:
  by_tool_overlap[arm]={}
  for seen in [True,False]:
   rr=[r for r in compare['details'][arm] if r['panel']=='development24' and (refs[r['id']]['tool_name'] in train_tools)==seen]
   by_tool_overlap[arm]['seen_tools' if seen else 'unseen_tools']={'n':len(rr),'strict':sum(r['strict'] for r in rr),'truncated':sum(r['truncated'] for r in rr),'invalid':sum(r['invalid'] for r in rr),'mean_generated_tokens':statistics.mean(r['tokens'] for r in rr) if rr else None}
 for panel in ['development24','old64']:
  rr=[r for r in inp if r['panel']==panel];coverage[panel]={'rows':len(rr),'training_tool_overlap_rows':sum(refs[r['id']]['tool_name'] in train_tools for r in rr),'tools':dict(collections.Counter(refs[r['id']]['tool_name'] for r in rr))}
 report={'status':'COMPLETE_VERIFIED','GPU':receipt['GPU'],'wall_seconds':receipt['seconds'],'training':train,'summary':compare['summary'],'retention':compare['retention'],'paired':paired,'output_diagnostics':diagnostic,'coverage':coverage,'DEV_tool_overlap_diagnostic':by_tool_overlap,'nonthinking_control':{'summary':control_summary,'evaluation_seconds':control['seconds'],'paired':control_paired,'old_correct_retention':control_retention,'training_updates':0,'scope':'Additional prompt-mode diagnostic; not the preregistered primary baseline'},'native_score_components':components,'adapter_tensor_checks':adapter_checks,'local_rescoring_matches_cluster':True,'initial_adapters_identical':True,'adapter_reload_hashes_verified':True,'training_order_verified':True,'official_TEST_queries':0,'confirmation_queries':0,'no_promotion':True}
 (RUN/'audit-analysis-private.json').write_text(json.dumps(report,indent=2)+'\n');(RUN/'changed-cases-private.json').write_text(json.dumps(changed,indent=2)+'\n')
 print(json.dumps(report,indent=2))
if __name__=='__main__':main()
