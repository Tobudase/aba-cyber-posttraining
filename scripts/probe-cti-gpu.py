#!/usr/bin/env python3
"""Bounded GPU/runtime inspection. No credentials, hostname, or raw environment."""
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError,version
import json
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
report={'checked_at_utc':datetime.now(timezone.utc).isoformat(), 'resources_modified':False,
        'official_test_rows':0,'packages':{},'disk_free_bytes':shutil.disk_usage(ROOT).free}
for name in ['torch','transformers','peft','accelerate','bitsandbytes']:
    try: report['packages'][name]=version(name)
    except PackageNotFoundError: report['packages'][name]=None
try:
    r=subprocess.run(['nvidia-smi','--query-gpu=name,memory.total,driver_version','--format=csv,noheader'],capture_output=True,text=True,timeout=20)
    report['nvidia_smi_returncode']=r.returncode
    report['nvidia_smi_gpu_summary']=r.stdout.strip()[:2000]
except (FileNotFoundError,subprocess.TimeoutExpired):report['nvidia_smi_available']=False
try:
    import torch
    report['cuda_available']=torch.cuda.is_available()
    report['torch_cuda_build']=torch.version.cuda
    if report['cuda_available']:
        report['gpus']=[{'index':i,'name':torch.cuda.get_device_name(i),
            'total_bytes':torch.cuda.get_device_properties(i).total_memory} for i in range(torch.cuda.device_count())]
        a=torch.arange(1024,device='cuda',dtype=torch.float32)
        report['cuda_tensor_check']=float((a+a)[-1])==2046.0
        torch.cuda.synchronize()
except ImportError:report['cuda_available']=False
report['status']='PASSED_GPU_TENSOR_CHECK' if report.get('cuda_tensor_check') else 'GPU_NOT_YET_VERIFIED'
dest=ROOT/'docs/verification/cti-datahub-gpu-probe.json';dest.parent.mkdir(parents=True,exist_ok=True)
dest.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
