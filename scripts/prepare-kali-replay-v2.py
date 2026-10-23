"""Author bounded GNU utility replay tasks, independent of benchmark answers."""
import json,shlex,importlib.util
from pathlib import Path
from benchkit import ROOT,kali_prompts,native_kali,strict_option_values,row_fingerprint,artifact_spec,write_json,write_jsonl,sha,load_jsonl

def tasks():
 out=[]
 def add(family,query,argv,optional,positional,fixtures,expected):
  out.append(dict(family=family,query=query,argv=argv,optional_args=optional,positional_args=positional,fixtures=fixtures,expected=expected))
 for v in ['amber','cedar']:
  add('basename',f'Print the final filename component of path /lab/{v}/records.csv using basename.',['basename',f'/lab/{v}/records.csv'],{},[f'/lab/{v}/records.csv'],{},'records.csv\n')
  add('basename-suffix',f'Use basename to remove directory components and suffix .log from /lab/{v}/audit.log.',['basename',f'/lab/{v}/audit.log','.log'],{},[f'/lab/{v}/audit.log','.log'],{},'audit\n')
  add('dirname',f'Use dirname to print the parent path of /lab/{v}/results.txt.',['dirname',f'/lab/{v}/results.txt'],{},[f'/lab/{v}/results.txt'],{},f'/lab/{v}\n')
  file=v+'.txt'
  add('cut-fields',f'Use cut to print comma-delimited fields 1 and 3 from {file}.',['cut','-d',',','-f','1,3',file],{'-d':',','-f':'1,3'},[file],{file:'alpha,beta,gamma\ndelta,epsilon,zeta\n'},'alpha,gamma\ndelta,zeta\n')
  add('cut-characters',f'Use cut to output characters 2 through 4 from each ASCII line in {file}.',['cut','-c','2-4',file],{'-c':'2-4'},[file],{file:'ABCDE\n12345\n'},'BCD\n234\n')
  a,b=v+'_left.txt',v+'_right.txt'
  add('paste',f'Use paste to merge corresponding lines from {a} and {b}, separating columns with a colon.',['paste','-d',':',a,b],{'-d':':'},[a,b],{a:'a\nb\n',b:'1\n2\n'},'a:1\nb:2\n')
  n=3 if v=='amber' else 4
  add('sequence',f'Use seq to print integers from {n} through {n+4} in steps of two, one number per line.',['seq',str(n),'2',str(n+4)],{},[str(n),'2',str(n+4)],{},f'{n}\n{n+2}\n{n+4}\n')
  add('expression',f'Use expr to compute {n} plus 7 and print the integer result.',['expr',str(n),'+','7'],{},[str(n),'+','7'],{},str(n+7)+'\n')
  add('expand',f'Use expand to convert tabs in {file} to spaces at tab stops every four columns.',['expand','-t','4',file],{'-t':'4'},[file],{file:'a\tb\n'},'a   b\n')
  add('fold',f'Use fold to wrap ASCII lines in {file} at a width of four columns.',['fold','-w','4',file],{'-w':'4'},[file],{file:'abcdefghij\n'},'abcd\nefgh\nij\n')
  add('unique-duplicates',f'Use uniq to output one copy of each adjacent repeated line in {file}, omitting lines occurring only once.',['uniq','-d',file],{'-d':None},[file],{file:'a\na\nb\nc\nc\n'},'a\nc\n')
  add('common-lines',f'Using comm with C-locale-sorted {a} and {b}, print only lines common to both files.',['comm','-1','-2',a,b],{'-1':None,'-2':None},[a,b],{a:'a\nb\nd\n',b:'b\nc\nd\n'},'b\nd\n')
  add('join',f'Use join to combine {a} and {b} on their default first whitespace-delimited field; both are sorted by that field in C locale.',['join',a,b],{},[a,b],{a:'a red\nb blue\n',b:'a 1\nb 2\n'},'a red 1\nb blue 2\n')
  add('numeric-sort',f'Use sort to order integer lines in {file} numerically in descending order.',['sort','-n','-r',file],{'-n':None,'-r':None},[file],{file:'2\n10\n1\n'},'10\n2\n1\n')
  add('printf',f'Use printf with a string format to print {v} followed by a newline.',['printf','%s\\n',v],{},['%s\\n',v],{},v+'\n')
  number=21 if v=='amber' else 35
  add('factor',f'Use factor to print the prime factorization of {number}.',['factor',str(number)],{},[str(number)],{},f'{number}: '+('3 7' if number==21 else '5 7')+'\n')
 return out

def main():
 source=json.loads((ROOT/'docs/verification/kali-replay-source-2026-10-23.json').read_text())
 raw=(ROOT/'.tools/coreutils-reference/coreutils.texi').read_bytes();assert sha(raw)==source['sha256']
 protected=[r for name in ['kali-domain-dev-v1','kali-external-dev'] for split in ['dev_search','dev_confirm'] for r in load_jsonl(ROOT/f'data/benchkit/{name}/{split}.jsonl')]
 protected_tools={r['native_label']['tool_name'] for r in protected}
 generated=[];meta={}
 for i,t in enumerate(tasks()):
  tool=t['argv'][0]
  if tool in protected_tools:raise ValueError('Replay must use tools outside all protected sets')
  assert ('@node '+tool+' invocation').encode() in raw
  identifier=f'kali-replay-v2-{i:03d}'
  generated.append({'custom_id':identifier,'query':t['query'],'tool_name':tool,'ground_truth_command':shlex.join(t['argv']),'optional_args':t['optional_args'],'positional_args':t['positional_args']});meta[identifier]=t
 prompts,labels=kali_prompts(generated);rows=[];scorer=native_kali()
 for x in generated:
  i=x['custom_id'];target='<output>'+x['ground_truth_command']+'</output>'
  assert scorer.score_one(labels[i],target)['exact_match']==1 and strict_option_values(labels[i],target,scorer)
  rows.append({'id':i,'benchmark':'kali','task':'unrestricted','split':'train','training_eligible':True,'official_test':False,'self_authored':True,'messages':prompts[i],'target':target,'native_label':labels[i],'group_id':'replay:'+meta[i]['family'],'template_family':meta[i]['family'],'source_url':source['source_url'],'source_sha256':source['sha256'],'quality':'AUTHORED_SOURCE_SILVER_EXECUTION_PENDING','input_sha256':row_fingerprint(prompts[i]),'fixture':{'files':meta[i]['fixtures'],'argv':meta[i]['argv'],'expected_stdout':meta[i]['expected']}})
 directory=ROOT/'data/benchkit/kali-replay-v2';directory.mkdir(exist_ok=True)
 write_jsonl(directory/'train.jsonl',rows)
 write_json(directory/'manifest.json',{'schema':'benchkit.dataset.v1','benchmark':'kali','official_test':False,'splits':{'train':artifact_spec(directory/'train.jsonl',rows)},'source':source,'protected_tool_overlap':0,'limitations':['32rows from16correlated families; original authored examples grounded in GNU documentation.','Not expert-reviewed; task-specific replay intentionally excludes all protected tool names.','No claim that unrelated utility replay alone preserves tshark knowledge.']})
 print(json.dumps({'rows':len(rows),'families':len({r['template_family'] for r in rows}),'protected_tool_overlap':0}))
if __name__=='__main__':main()
