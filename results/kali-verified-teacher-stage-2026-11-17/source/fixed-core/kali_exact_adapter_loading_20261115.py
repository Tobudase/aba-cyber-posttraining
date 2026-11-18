"""Restore exact FP32 LoRA weights after PEFT's BF16 additional-adapter load."""
def load_exact_adapter(model,path,name,is_trainable=True):
    import torch
    from pathlib import Path
    from peft import get_peft_model_state_dict,set_peft_model_state_dict
    from safetensors.torch import load_file
    source=load_file(str(Path(path)/'adapter_model.safetensors'))
    if not source or any(v.dtype!=torch.float32 or '.lora_' not in k for k,v in source.items()):raise ValueError('This audited loader expects FP32 LoRA-only task weights')
    if 'bias' in name or any(name in key for key in source):raise ValueError('Adapter name collides with PEFT state-dict filtering or base parameter keys')
    if any(other!=name and (name in other or other in name) for other in model.peft_config):raise ValueError('Adapter names must not be substrings of each other in this PEFT version')
    if name not in model.peft_config:model.load_adapter(path,adapter_name=name,is_trainable=is_trainable)
    before=get_peft_model_state_dict(model,adapter_name=name)
    if set(before)!=set(source):raise ValueError('Adapter key set differs from checkpoint')
    before_difference=max(float((v.detach().cpu().float()-source[k]).abs().max()) for k,v in before.items())
    for key,param in model.named_parameters():
        if '.lora_' in key and '.'+name+'.' in key and param.dtype!=torch.float32:param.data=param.data.float()
    set_peft_model_state_dict(model,source,adapter_name=name)
    actual=get_peft_model_state_dict(model,adapter_name=name)
    if set(actual)!=set(source) or not all(torch.equal(v.detach().cpu(),source[k]) for k,v in actual.items()):raise ValueError('Exact adapter restore failed')
    return {'adapter':name,'tensors':len(actual),'before_max_abs':before_difference,'after_max_abs':0.,'dtype':'FP32','exact_source_equality':True}
