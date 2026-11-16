"""Pure ordinary-node eligibility; no quota, taint or reservation bypass."""
def eligible_nodes(nodes,products,region="us-west"):
    result=[]
    for node in nodes:
        labels=node['metadata'].get('labels',{});spec=node['spec']
        if labels.get('nvidia.com/gpu.product') not in products:continue
        if labels.get('topology.kubernetes.io/region')!=region:continue
        if int(labels.get('nvidia.com/cuda.driver.major','0'))<570:continue
        if spec.get('unschedulable'):continue
        if any(t['effect'] in ['NoSchedule','NoExecute'] for t in spec.get('taints',[])):continue
        if not any(c['type']=='Ready' and c['status']=='True' for c in node['status']['conditions']):continue
        if node['metadata']['name']=='nautilus-ext-gpu01.fullerton.edu':continue
        # Affinity matches hostname label, not an assumed equality to node name.
        host=labels.get('kubernetes.io/hostname')
        if host:result.append(host)
    return sorted(set(result))
