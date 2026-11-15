import sys,unittest
from pathlib import Path
import torch
import torch.nn.functional as F
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from kali_stable_objective_20261114 import objective_sums,accumulation_loss,supervised_count

class ObjectiveTests(unittest.TestCase):
    def test_direction_and_reference_gradient(self):
        a=torch.tensor([[[.4,-.3],[0.,0.]]],requires_grad=True)
        b=torch.tensor([[[2.,-1.],[1.,1.]]],requires_grad=True)
        y=torch.tensor([[-100,1]])
        _,kl,_=objective_sums(a,y,b)
        p=a[0,0].softmax(-1);q=b[0,0].detach().softmax(-1)
        expected=(p*(p.log()-q.log())).sum()
        reverse=(q*(q.log()-p.log())).sum()
        torch.testing.assert_close(kl,expected)
        self.assertGreater(abs(float(kl-reverse)),.01)
        grad=torch.autograd.grad(kl,a,retain_graph=True)[0]
        direct=torch.autograd.grad(expected,a)[0]
        torch.testing.assert_close(grad,direct)
        kl.backward();self.assertIsNone(b.grad)

    def test_causal_mask_and_eos(self):
        torch.manual_seed(4)
        a=torch.randn(1,5,7,requires_grad=True);b=torch.randn_like(a)
        y=torch.tensor([[-100,-100,2,6,-100]])
        ce,kl,n=objective_sums(a,y,b)
        self.assertEqual(n,2)
        torch.testing.assert_close(ce,F.cross_entropy(a[0,1:3],torch.tensor([2,6]),reduction='sum'))
        (ce+.01*kl).backward()
        self.assertEqual(int(torch.count_nonzero(a.grad[:,[0,3,4]])),0)
        self.assertGreater(int(torch.count_nonzero(a.grad[:,[1,2]])),0)

    def test_identity_and_chunks(self):
        torch.manual_seed(5);a=torch.randn(2,8,13,requires_grad=True);b=torch.randn_like(a)
        y=torch.zeros(2,8,dtype=torch.long);y[:,:3]=-100
        self.assertLess(abs(float(objective_sums(a,y,a)[1])),1e-6)
        one=objective_sums(a,y,b,1);many=objective_sums(a,y,b,32)
        torch.testing.assert_close(one[0],many[0]);torch.testing.assert_close(one[1],many[1])

    def test_uneven_microbatches_match_full_batch_gradient(self):
        torch.manual_seed(8);model=torch.nn.Linear(3,7,bias=False)
        x=torch.randn(3,6,3);y=torch.tensor([[-100,-100,-100,-100,-100,2],[-100,1,2,3,4,5],[-100,-100,1,2,3,4]])
        ref=torch.randn(3,6,7);total=supervised_count(y)
        loss,_=accumulation_loss(model(x),y,total,.03,ref);loss.backward();full=model.weight.grad.clone()
        model.zero_grad(set_to_none=True)
        for lo,hi in [(0,1),(1,3)]:
            loss,_=accumulation_loss(model(x[lo:hi]),y[lo:hi],total,.03,ref[lo:hi]);loss.backward()
        torch.testing.assert_close(model.weight.grad,full,atol=1e-6,rtol=1e-5)

    def test_invalid_masks_and_missing_reference(self):
        a=torch.randn(1,3,5,requires_grad=True)
        with self.assertRaises(ValueError):objective_sums(a,torch.full((1,3),-100))
        y=torch.tensor([[-100,1,2]])
        with self.assertRaises(ValueError):accumulation_loss(a,y,1)
        with self.assertRaises(ValueError):accumulation_loss(a,y,2,.01)
        with self.assertRaises(ValueError):accumulation_loss(a,y,2,float('nan'))

if __name__=='__main__':unittest.main()
