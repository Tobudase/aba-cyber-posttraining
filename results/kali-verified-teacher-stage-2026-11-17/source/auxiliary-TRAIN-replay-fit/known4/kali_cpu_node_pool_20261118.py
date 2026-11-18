"""Ordinary AMD64 CPU-only pool; never consumes a GPU node or adds tolerations."""
import json
from kali_execution_jobs_20261114 import k


def eligible_cpu_only(nodes):
    result=[]
    for node in nodes:
        labels=node['metadata'].get('labels',{})
        if labels.get('kubernetes.io/arch')!='amd64':continue
        if labels.get('nvidia.com/gpu.product') or labels.get('feature.node.kubernetes.io/pci-10de.present')=='true':continue
        if any(key.startswith(('nvidia.com/','amd.com/','habana.ai/')) and str(value) not in ['0','0m']
               for key,value in node['status'].get('allocatable',{}).items()):continue
        if node['spec'].get('unschedulable') or any(t['effect'] in ['NoSchedule','NoExecute'] for t in node['spec'].get('taints',[])):continue
        if not any(c['type']=='Ready' and c['status']=='True' for c in node['status'].get('conditions',[])):continue
        result.append(labels.get('kubernetes.io/hostname',node['metadata']['name']))
    return sorted(result)


def ordinary_cpu_nodes():
    nodes=eligible_cpu_only(json.loads(k('get','nodes','-o','json').stdout)['items'])
    assert nodes,'No ordinary healthy CPU-only nodes; do not silently consume GPU nodes'
    return nodes
