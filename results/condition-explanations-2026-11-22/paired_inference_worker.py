"""Free, paired inference on same-source diagnostics. Only pre-existing adapters are loaded."""
import hashlib,json
from pathlib import Path
import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM,AutoTokenizer
from kali_framed_artifacts_20261117 import emit
plan=json.loads(Path('/input/pairs-task.json').read_text())
tok=AutoTokenizer.from_pretrained('/scratch/model',local_files_only=True,padding_side='left')
tok.pad_token=tok.eos_token
base=AutoModelForCausalLM.from_pretrained('/scratch/model',local_files_only=True,torch_dtype=torch.bfloat16,attn_implementation='sdpa').to('cuda').eval()
prompts=[tok.apply_chat_template([{'role':'system','content':plan['system']},{'role':'user','content':r['prompt']}],tokenize=False,add_generation_prompt=True,enable_thinking=True) for r in plan['rows']]
batch=tok(prompts,return_tensors='pt',add_special_tokens=False,padding=True).to('cuda')
out={}; model=base
for tag,target in plan['adapters'].items():
    if target is not None:
        p=Path('/cache')/target['folder']/tag.replace('A16','A-16').replace('A64','A-64').replace('B64','B-64').replace('C64','C-64')
        assert hashlib.sha256((p/'adapter_model.safetensors').read_bytes()).hexdigest()==target['weights']
        if model is base:
            model=PeftModel.from_pretrained(base,p,adapter_name=tag).eval()
        else:model.load_adapter(p,adapter_name=tag)
        model.set_adapter(tag)
    scores={}
    stops=model.generation_config.eos_token_id
    if isinstance(stops,int):stops=[stops]
    for seed in plan['seeds']:
        torch.manual_seed(seed)
        with torch.inference_mode():
            y=model.generate(**batch,do_sample=True,temperature=.6,top_p=.95,top_k=20,min_p=0.,max_new_tokens=4096,pad_token_id=tok.pad_token_id)
        vals={}
        for q,tail in zip(plan['rows'],y[:,batch.input_ids.shape[1]:].tolist()):
            n=next((j for j,t in enumerate(tail) if t in stops),len(tail))
            decoded=tok.decode(tail[:n],skip_special_tokens=False)
            pre,marker,visible=decoded.rpartition('</think>')
            vals[q['name']]=dict(ended=n<len(tail),closed=bool(marker),tokens=n,visible=visible.strip() if marker else decoded.strip())
        scores[str(seed)]=vals
        print('assessed',tag,seed,[v['tokens'] for v in vals.values()],flush=True)
    out[tag]=scores
emit(dict(draws=out,device=torch.cuda.get_device_name()),'PAIREDEVAL')
