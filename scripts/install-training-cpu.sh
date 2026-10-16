#!/usr/bin/env bash
set -euo pipefail
export OMP_NUM_THREADS=2
export MKL_NUM_THREADS=2
export HF_HUB_DISABLE_TELEMETRY=1
export PIP_DISABLE_PIP_VERSION_CHECK=1
TRAINING_ROOT="${TRAINING_ROOT:-$HOME/cybergym-training}"
mkdir -p "$TRAINING_ROOT/logs"
cd "$TRAINING_ROOT"
test -f configs/training-requirements.in
python3 - <<'PY'
import platform, shutil
if platform.system() != 'Linux' or platform.machine() != 'x86_64':
    raise SystemExit('This bounded CPU installer requires Linux x86_64')
if shutil.disk_usage('.').free < 5 * 1024**3:
    raise SystemExit('At least 5 GiB free disk is required')
PY
python3 -m venv .venv
# A bounded CPU test should not download CUDA runtime packages.
timeout 600 .venv/bin/python -m pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu 'torch==2.8.0' > logs/torch-install.log 2>&1
timeout 600 .venv/bin/python -m pip install --no-cache-dir -r configs/training-requirements.in > logs/runtime-install.log 2>&1
.venv/bin/python -m pip check > logs/pip-check.txt 2>&1
.venv/bin/python -m pip freeze > logs/requirements-linux-cpu.lock.txt
.venv/bin/python - <<'PY'
import json, platform
from importlib.metadata import version
import torch
from transformers import Qwen3Config, Qwen3ForCausalLM
from trl import SFTConfig, SFTTrainer
from peft import LoraConfig, PeftModel
report={'platform':platform.platform(),'python':platform.python_version(),
        'versions':{name:version(name) for name in ['torch','transformers','trl','peft','accelerate','datasets','bitsandbytes','jinja2','tokenizers']},
        'torch_cuda_available':torch.cuda.is_available(),
        'torch_cuda_build':torch.version.cuda,
        'imports_passed':True,'training_executed':False}
with open('logs/runtime-imports.json','w') as f: json.dump(report,f,indent=2)
print(json.dumps(report,indent=2))
PY
