"""Token-normalized SFT plus frozen-E0 KL on old command-body tokens only."""
import torch
from kali_stable_objective_20261114 import objective_sums,supervised_count

def loss_parts(student_logits,labels,kl_labels=None,reference_logits=None):
    ce,_,n=objective_sums(student_logits,labels)
    kl=student_logits.new_zeros((),dtype=torch.float32);k=0
    if kl_labels is not None:
        k=supervised_count(kl_labels)
        if k:
            if reference_logits is None:raise ValueError('Body KL requires frozen E0 reference')
            _,kl,_=objective_sums(student_logits,kl_labels,reference_logits)
    return ce,kl,n,k

def normalized_loss(ce,kl,total_ce,total_kl,beta):
    if total_ce<=0 or beta<0 or (beta and total_kl<=0):raise ValueError('Invalid accumulation normalization')
    return ce/total_ce+(beta*kl/total_kl if beta else 0)

def check_cpu():
    import torch.nn.functional as F
    torch.manual_seed(42);student=torch.randn(1,5,7,requires_grad=True);reference=torch.randn(1,5,7,requires_grad=True)
    labels=torch.tensor([[-100,-100,1,2,3]]);body=torch.tensor([[-100,-100,-100,2,-100]])
    ce,kl,n,k=loss_parts(student,labels,body,reference)
    expected=F.cross_entropy(student[0,1:4],labels[0,2:],reduction='sum')
    ls=F.log_softmax(student[0,2],dim=-1);lr=F.log_softmax(reference[0,2].detach(),dim=-1);manual=(ls.exp()*(ls-lr)).sum()
    checks={'causal_completion_CE':bool(torch.allclose(ce,expected)),'command_mask_and_direction':k==1 and n==3 and bool(torch.allclose(kl,manual)),
        'beta0_exact_CE':bool(torch.equal(normalized_loss(ce,kl,n,k,0),ce/n))}
    normalized_loss(ce,kl,n,k,.03).backward();checks['reference_no_gradient']=reference.grad is None;checks['student_has_gradient']=bool(student.grad.abs().sum()>0)
    # Two different target lengths, one replay row: microbatch accumulation must
    # equal the explicitly summed full-window objective and gradients.
    a=torch.tensor(.4,requires_grad=True);b=a.detach().clone().requires_grad_(True)
    ce1=(a-1).pow(2)*2;ce2=(a+.5).pow(2)*5;kk=(a-.1).pow(2)*3
    normalized_loss(ce1,kk,7,3,.2).backward(retain_graph=True);normalized_loss(ce2,a*0,7,3,0).backward()
    ((2*(b-1).pow(2)+5*(b+.5).pow(2))/7+.2*(3*(b-.1).pow(2))/3).backward()
    checks['unequal_length_accumulation_gradient']=bool(torch.allclose(a.grad,b.grad))
    assert all(checks.values()),checks
    return {'status':'PASS','checks':checks,'scope':'CPU math and masking; real PEFT reference-disable equivalence remains a separate GPU preflight.'}

if __name__=='__main__':
    import json
    print(json.dumps(check_cpu(),indent=2))
