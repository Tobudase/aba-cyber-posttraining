import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from kali_qwen_gpu_placement_20261115 import eligible_nodes
class Placement(unittest.TestCase):
 def node(self,name='one',product='GPU'):
  return {'metadata':{'name':name,'labels':{'kubernetes.io/hostname':name+'-host','nvidia.com/gpu.product':product,'topology.kubernetes.io/region':'us-west','nvidia.com/cuda.driver.major':'615'}},'spec':{},'status':{'conditions':[{'type':'Ready','status':'True'}]}}
 def test_keep_all_matching_not_final_iteration(self):
  nodes=[self.node('first'),self.node('second'),self.node('last','wrong')]
  self.assertEqual(eligible_nodes(nodes,['GPU']),['first-host','second-host'])
 def test_no_reservation_or_unready_fallback(self):
  nodes=[self.node(str(i)) for i in range(5)];nodes[0]['spec']['taints']=[{'effect':'NoSchedule','key':'reservation'}];nodes[1]['spec']['unschedulable']=True;nodes[2]['status']['conditions'][0]['status']='False';nodes[3]['metadata']['labels']['topology.kubernetes.io/region']='us-east';nodes[4]['metadata']['labels']['nvidia.com/cuda.driver.major']='550'
  self.assertEqual(eligible_nodes(nodes,['GPU']),[])
if __name__=='__main__':unittest.main()
