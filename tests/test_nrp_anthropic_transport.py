import copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from nrp_anthropic_transport import encode_events,route_target,route_payload
class TransportTests(unittest.TestCase):
 def test_native_sdk_beta_query_preserved(self):
  self.assertEqual(('/v1/messages','/v1/messages?beta=true'),route_target('/v1/messages?beta=true'))
  self.assertEqual(('/v1/messages/count_tokens','/v1/messages/count_tokens?beta=true'),route_target('/v1/messages/count_tokens?beta=true'))
 def test_unknown_routes_queries_and_external_targets_fail_closed(self):
  for target in ['/v1/other','https://example.com/v1/messages','//example.com/v1/messages','/v1/messages?token=secret','/v1/messages?beta=false','/v1/messages?beta=true&beta=true','/v1/messages#fragment']:
   with self.assertRaises(ValueError):route_target(target)
 def message(self,content):return {'id':'message1','type':'message','role':'assistant','model':'fixed','content':content,'stop_reason':'tool_use','stop_sequence':None,'usage':{'input_tokens':20,'output_tokens':10}}
 def events(self,m):return [json.loads(x[6:]) for x in encode_events(m).decode().splitlines() if x.startswith('data: ')]
 def test_mixed_text_and_two_tools_roundtrip_exactly(self):
  original=self.message([{'type':'text','text':'Ready.\n'},{'type':'tool_use','id':'first','name':'record_ping','input':{'value':'ONE','unicode':'中文','n':1}},{'type':'text','text':'\n'},{'type':'tool_use','id':'second','name':'record_ping','input':{'value':'TWO'}}]);before=copy.deepcopy(original);blocks=[];active={}
  for e in self.events(original):
   t=e['type'];i=e.get('index')
   if t=='content_block_start':active[i]=e['content_block'].copy();blocks.append(active[i])
   if t=='content_block_delta':
    d=e['delta'];b=active[i]
    if d['type']=='text_delta':self.assertEqual('text',b['type']);b['text']+=d['text']
    elif d['type']=='input_json_delta':self.assertEqual('tool_use',b['type']);b['input']=json.loads(d['partial_json'])
  self.assertEqual(original['content'],blocks);self.assertEqual(before,original)
 def test_reasoning_and_signatures_preserved(self):
  b=[{'type':'thinking','thinking':'reason','signature':'sig'},{'type':'redacted_thinking','data':'opaque'}]
  self.assertEqual(b,[e['content_block'] for e in self.events(self.message(b)) if e['type']=='content_block_start'])
 def test_explicit_model_alias_preserves_message_and_tools(self):
  p={'model':'gpt-oss-120b','messages':[{'role':'user','content':'neutral'}],'tools':[{'name':'safe_tool','input_schema':{'type':'object'}}]};before=copy.deepcopy(p);q=route_payload(p);self.assertEqual(p,before);self.assertEqual(q,{**p,'model':'gpt-oss'});self.assertIs(q['messages'],p['messages']);self.assertIs(q['tools'],p['tools']);self.assertEqual(route_payload({'model':'qwen3-small'}),{'model':'qwen3-small'})
 def test_invalid_blocks_fail_closed(self):
  for b in [{'type':'unknown','text':'x'},{'type':'text','text':None},{'type':'tool_use','id':'x','name':'run','input':'not a JSON object'}]:
   with self.assertRaises(ValueError):encode_events(self.message([b]))
 def test_usage_and_stop_reason_kept(self):
  m=self.message([]);ev=self.events(m);self.assertEqual(m['usage'],ev[-2]['usage']);self.assertEqual(m['stop_reason'],ev[-2]['delta']['stop_reason']);self.assertEqual('message_stop',ev[-1]['type'])
if __name__=='__main__':unittest.main()
