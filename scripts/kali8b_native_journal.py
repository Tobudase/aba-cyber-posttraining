
from collections import Counter
from dataclasses import asdict
import json,pathlib,sys
from aibuildai_version import preload_source_runtime
preload_source_runtime()
from infra.postgresql import ensure_postgresql
ensure_postgresql()
from engine.event.store import open_search_store,iter_run_events
from engine.run_query import read_run_head
run_id=next(pathlib.Path('/mnt/aba-scratch/study/playground/kali8b-verified64').iterdir()).name.rsplit('_',1)[-1]
root=pathlib.Path('/mnt/aba-scratch/study/playground/kali8b-verified64')
homes=list(root.glob('*_'+run_id))
assert len(homes)==1
result={'run_id':run_id,'head':asdict(read_run_head(run_id,homes[0])),
        'recent_backend_logs':[],'recent_tools':[],'recent_text':[],'rate_limits':[],'event_counts':{},'tool_counts':{},'tool_errors':[],'finalizer_tools':[],'structured_output_results':[],'turns':[],'budget_notifications':[],'started_actions':[],'actions':[],'failures':[],'program_attempts':[],'usage_events':[]}
events=Counter(); tools=Counter(); tool_names={}
app=open_search_store(run_id,read_only=True)
try:
 for event in iter_run_events(app):
  name=type(event).__name__; events[name]+=1
  if name=='RateLimitPaused':result['rate_limits'].append(json.loads(json.dumps(asdict(event),default=str)))
  elif name=='TextDelta':result['recent_text']=(result['recent_text']+[str(asdict(event))[-1400:]])[-3:]
  elif name=='ToolUseStart':
   result['recent_tools']=(result['recent_tools']+[{'kind':'start','fields':str(asdict(event))[-2200:]}])[-12:]
   tools[event.name]+=1;tool_names[event.tool_use_id]=event.name
   if '/finalizer_' in str(event.target):result['finalizer_tools'].append({'kind':'start','tool':event.name,'fields':str(asdict(event))[-2200:]})
  elif name=='ToolUseEnd':
   result['recent_tools']=(result['recent_tools']+[{'kind':'end','tool':tool_names.get(event.tool_use_id),'fields':str(event.output)[-2200:]}])[-12:]
   if '/finalizer_' in str(event.target):result['finalizer_tools'].append({'kind':'end','tool':tool_names.get(event.tool_use_id),'output':str(event.output)[-1600:]})
   if event.is_error:result['tool_errors'].append({'tool':tool_names.get(event.tool_use_id),'output':str(event.output)[-1200:]})
   if tool_names.get(event.tool_use_id)=='StructuredOutput':result['structured_output_results'].append({'target':event.target,'output':str(event.output)[-4000:]})
  elif name=='ActionStarted':result['started_actions'].append(str(event.target))
  elif name=='ActionCompleted':result['actions'].append({'target':event.target,'ordinal':event.ordinal,'output':event.output})
  elif name=='ExecutionFailureRecorded':result['failures'].append({'target':event.target,'kind':str(event.failure.kind),'reason':event.failure.reason})
  elif name=='ProgramAttemptRecorded':result['program_attempts'].append({'target':event.target,'return_code':event.return_code})
  elif name=='UsageDelta':result['usage_events'].append({'target':event.target,'model':event.model,'input_tokens':event.input_tokens,'output_tokens':event.output_tokens,'cumulative':event.cumulative})
  elif name=='TurnComplete':result['turns'].append({'target':event.target,'elapsed_s':event.ts,'stop_reason':event.stop_reason,'has_structured_output':event.structured_output is not None})
  elif name=='BackendLog':
   result['recent_backend_logs']=(result['recent_backend_logs']+[{'source':event.source,'target':event.target,'elapsed_s':event.ts,'text':event.text[-2000:]}])[-8:]
   if event.source=='budget':result['budget_notifications'].append({'target':event.target,'elapsed_s':event.ts,'text':event.text})
finally:app.close()
result['event_counts']=dict(events);result['tool_counts']=dict(tools)
print(json.dumps(result))
