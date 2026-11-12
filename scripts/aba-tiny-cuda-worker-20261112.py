import torch,json,io,hashlib
assert torch.cuda.is_available()
torch.manual_seed(42);torch.cuda.manual_seed_all(42)
w=torch.nn.Parameter(torch.zeros((8,8),device='cuda'));x=torch.arange(8,device='cuda');y=(x+1)%8
opt=torch.optim.SGD([w],lr=.2)
initial=torch.nn.functional.cross_entropy(w[x],y).item()
for step in range(32):
 opt.zero_grad();loss=torch.nn.functional.cross_entropy(w[x],y);loss.backward();assert torch.isfinite(w.grad).all() and w.grad.abs().sum()>0;opt.step()
final=torch.nn.functional.cross_entropy(w[x],y).item();buf=io.BytesIO();torch.save(w.detach().cpu(),buf);packed=buf.getvalue();loaded=torch.load(io.BytesIO(packed),weights_only=True).to('cuda');diff=(loaded-w).abs().max().item()
assert final<initial and diff==0
print(json.dumps({'status':'TINY_CUDA_WORKER_PASS','gpu':torch.cuda.get_device_name(0),'optimizer_steps':32,'initial_train_nll':initial,'final_train_nll':final,'reload_max_abs_diff':diff,'artifact_sha256':hashlib.sha256(packed).hexdigest(),'weights':w.detach().cpu().tolist(),'weights_l1_change':w.detach().abs().sum().item(),'official_TEST_rows':0,'scope':'Synthetic engineering smoke only; no LLM or KaliBench model trained.'}))
