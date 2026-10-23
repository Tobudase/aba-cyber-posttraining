"""Finite CUDA/optimizer smoke; no model downloads, benchmark or idle loop."""
import json, subprocess, time
import torch
start=time.monotonic()
assert torch.cuda.is_available()
torch.manual_seed(42)
model=torch.nn.Linear(1024,1024,bias=False,device='cuda',dtype=torch.float32)
x=torch.randn(32,1024,device='cuda');target=torch.zeros_like(x)
optimizer=torch.optim.SGD(model.parameters(),lr=0.01)
first=None
for step in range(20):
 optimizer.zero_grad();loss=(model(x)-target).square().mean();loss.backward();optimizer.step()
 if first is None:first=float(loss.item())
torch.cuda.synchronize()
r={'status':'PASS_CUDA_OPTIMIZER_SMOKE','gpu':torch.cuda.get_device_name(0),'gpu_total_bytes':torch.cuda.get_device_properties(0).total_memory,'torch':torch.__version__,'cuda_build':torch.version.cuda,'optimizer_steps':20,'initial_loss':first,'final_loss':float(loss.item()),'peak_allocated_bytes':torch.cuda.max_memory_allocated(),'wall_seconds':time.monotonic()-start,'scope':'Synthetic linear-layer runtime check, not LLM training or benchmark evaluation','official_test_rows':0,'ABA_executed':False}
print(json.dumps(r),flush=True)
