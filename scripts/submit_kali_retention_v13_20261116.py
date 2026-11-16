"""One bounded, sequential replay-content study after verified v11/v12 completion."""
import datetime
import hashlib
import json
import sys
from kali_execution_jobs_20261114 import ROOT, OUT, k, submit, gpu_cache_conflicts, write


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def launch(name):
    data = ROOT / 'data/benchkit/kali-retention-v13-2026-11-16'
    prior = OUT / 'miw113-kali-objective-v11-r2-1116'
    path_study = OUT / 'miw113-kali-path-v12-1116'
    assert json.loads((prior / 'host.json').read_text()).get('resources_cleaned')
    assert json.loads((prior / 'export-audit.json').read_text())['all_weights_verified']
    assert json.loads((path_study / 'analysis.json').read_text())['status'] == 'COMPLETE_READ_ONLY_DIAGNOSIS'
    assert json.loads((path_study / 'host.json').read_text()).get('resources_cleaned')
    protocol = json.loads((data / 'protocol.json').read_text())
    assert sha(data / 'gpu-inputs.json.gz') == protocol['data_sha256']
    assert not (data / 'launch-freeze.json').exists()
    cfg = json.loads(json.loads((prior / 'objects.json').read_text())[0]['data']['config.json'])
    source = json.loads((prior / 'receipt.json').read_text())['checkpoints']['RK_step192']
    base_output = cfg['durable_output']
    cfg.update(anchor_adapter=cfg['source_adapter'], anchor_weights_sha256=cfg['source_weights_sha256'],
               anchor_config_sha256=cfg['source_config_sha256'])
    cfg.update(source_adapter=base_output + '/' + source['adapter_relative_path'],
               source_weights_sha256=source['weights_sha256'], source_config_sha256=source['config_sha256'])
    modules = ['kali_retention_body_v13_20261116.py', 'kali_rollout_distillation_20261115.py',
               'kali_stable_objective_20261114.py', 'kali_command_ngram_guard_20261115.py',
               'kali_exact_adapter_loading_20261115.py']
    worker = ROOT / 'scripts/kali_retention_worker_v13_20261116.py'
    cfg.update(data_directory=str(data.relative_to(ROOT)), inputs_gzip_sha256=protocol['data_sha256'],
               worker_sha256=sha(worker), module_sha256={n: sha(ROOT/'scripts'/n) for n in modules},
               durable_output='/cache/kali-functional-repair-20261115/' + name,
               recipe=protocol, maximum_optimizer_steps_total=192, maximum_generations=2200)
    pods = json.loads(k('get', 'pods', '-l', 'app.kubernetes.io/managed-by=miw113', '-o', 'json').stdout)['items']
    assert not gpu_cache_conflicts(pods, 'miw113-kali-cuda-cache-east')
    allowed = {n.replace(' ', '-') for n in cfg['model_protocol']['allowed_GPU_models']}
    nodes = []
    for n in json.loads(k('get', 'nodes', '-o', 'json').stdout)['items']:
        labels = n['metadata'].get('labels', {})
        if labels.get('nvidia.com/gpu.product') not in allowed or n['spec'].get('unschedulable'):
            continue
        if any(t['effect'] in ['NoSchedule', 'NoExecute'] for t in n['spec'].get('taints', [])):
            continue
        if n['metadata']['name'] == 'nautilus-ext-gpu01.fullerton.edu':
            continue
        if any(c['type'] == 'Ready' and c['status'] == 'True' for c in n['status']['conditions']):
            nodes.append(n['metadata']['name'])
    assert nodes
    write(data/'launch-freeze.json', {'at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                    'protocol_sha256': sha(data/'protocol.json'), 'config': cfg,
                                    'maximum_GPU_seconds': 10800, 'job': name})
    return submit(name, {'worker.py': worker.read_text(), 'config.json': json.dumps(cfg, indent=2)+'\n',
                         **{n: (ROOT/'scripts'/n).read_text() for n in modules}},
                  {'cpu': '2', 'memory': '14Gi', 'ephemeral-storage': '24Gi', 'nvidia.com/gpu': '1'},
                  cache=True, readonly=False, cache_claim='miw113-kali-cuda-cache-east', cache_region=None,
                  node_names=nodes, preferred_node_names=['suncave-14'],
                  binary_files={'inputs.json.gz': (data/'gpu-inputs.json.gz').read_bytes()}, runtime=10800)


if __name__ == '__main__':
    print(json.dumps(launch(sys.argv[1]), indent=2))
