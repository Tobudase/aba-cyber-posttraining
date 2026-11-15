"""Token-summed CE and student-to-reference KL for a NEW experiment only.

The caller freezes E0, computes its logits without gradients, and passes the
total supervised token count of the entire accumulation window. This module
does not change any historical recipe and does not itself update parameters.
"""
import math
import torch
import torch.nn.functional as F

def supervised_count(labels):
    if labels.ndim != 2:
        raise ValueError('Expected batch x sequence labels')
    return int((labels[:, 1:] != -100).sum().item())

def objective_sums(student_logits, labels, reference_logits=None, chunk_size=32):
    if student_logits.ndim != 3 or tuple(labels.shape) != tuple(student_logits.shape[:2]):
        raise ValueError('Incompatible logits and labels')
    if reference_logits is not None and reference_logits.shape != student_logits.shape:
        raise ValueError('Reference shape mismatch')
    if chunk_size < 1:
        raise ValueError('Invalid chunk size')
    count=supervised_count(labels)
    if count == 0:
        raise ValueError('No supervised next-token positions')
    ce=student_logits.new_zeros((),dtype=torch.float32)
    kl=student_logits.new_zeros((),dtype=torch.float32)
    targets=labels[:,1:]
    for start in range(0,student_logits.shape[1]-1,chunk_size):
        stop=min(start+chunk_size,student_logits.shape[1]-1)
        active=targets[:,start:stop] != -100
        if not bool(active.any()):
            continue
        logits=student_logits[:,start:stop][active].float()
        ce=ce+F.cross_entropy(logits,targets[:,start:stop][active],reduction='sum')
        if reference_logits is not None:
            log_student=F.log_softmax(logits,dim=-1)
            log_reference=F.log_softmax(reference_logits[:,start:stop][active].detach().float(),dim=-1)
            # Both student probability and log probability retain gradients.
            kl=kl+(log_student.exp()*(log_student-log_reference)).sum()
    return ce,kl,count

def accumulation_loss(student_logits, labels, total_update_tokens, beta=0.0,
                      reference_logits=None, chunk_size=32):
    if not math.isfinite(beta) or beta < 0:
        raise ValueError('Invalid KL coefficient')
    if beta and reference_logits is None:
        raise ValueError('KL requires frozen E0 reference logits')
    ce,kl,count=objective_sums(student_logits,labels,reference_logits,chunk_size)
    if isinstance(total_update_tokens,bool) or not isinstance(total_update_tokens,int) or total_update_tokens<count:
        raise ValueError('Use the full accumulation-window supervised token count')
    return (ce+beta*kl)/total_update_tokens,{'tokens':count,'ce_sum':float(ce.detach()),'kl_sum':float(kl.detach())}
