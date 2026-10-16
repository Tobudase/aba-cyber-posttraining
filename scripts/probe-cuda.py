#!/usr/bin/env python3
"""One bounded CUDA/BF16 hardware check; no model weights or training data."""
from datetime import datetime, timezone
import json
import time
import torch

if not torch.cuda.is_available():
    raise SystemExit('CUDA is not available')
torch.set_num_threads(1)
torch.cuda.set_device(0)
if not torch.cuda.is_bf16_supported():
    raise SystemExit('BF16 is not supported on the allocated device')
torch.manual_seed(42)
start = time.monotonic()
a = torch.randn(1024, 1024, device='cuda', dtype=torch.bfloat16)
b = torch.randn(1024, 1024, device='cuda', dtype=torch.bfloat16)
c = a @ b
torch.cuda.synchronize()
if not torch.isfinite(c).all().item():
    raise SystemExit('Non-finite CUDA result')
device = torch.cuda.get_device_properties(0)
print('CUDA_PROBE_RESULT=' + json.dumps({
    'checked_at': datetime.now(timezone.utc).isoformat(), 'status': 'PASSED',
    'scope': 'CUDA_BF16_RUNTIME_ONLY', 'torch_version': torch.__version__,
    'torch_cuda_build': torch.version.cuda, 'device_name': device.name,
    'device_memory_bytes': device.total_memory,
    'device_compute_capability': [device.major, device.minor],
    'bf16_matmul_finite': True, 'elapsed_seconds': round(time.monotonic() - start, 4),
    'peak_allocated_bytes': torch.cuda.max_memory_allocated(),
    'model_weights_downloaded': False, 'training_executed': False,
    'priority_class': 'opportunistic', 'preemption_possible': True
}), flush=True)
