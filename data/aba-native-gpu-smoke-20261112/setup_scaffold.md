# Operator-provided Setup recipe, before the run

These are fixture preparation hints, not training or score results. Keep all native baseline and boundary verifiers enabled. Do not train a sanity model or call train_client.py in Setup. Use Read/Write for protected task inputs; Bash cannot copy or modify protected inputs.

Expose exactly README.md, train.jsonl, base_model.json, train_client.py under PUBLIC. Keep dev.jsonl, evaluate.py, this setup helper and manifest private. The original task files remain immutable.

A thin PRIVATE score.py can be:

```python
import json,subprocess,sys
from pathlib import Path
def score(output_dir):
    r=subprocess.run([sys.executable,'/mnt/aba-scratch/smoke/task/evaluate.py','--model-path',str(Path(output_dir)/'final_model')],check=True,capture_output=True,text=True)
    return json.loads(r.stdout)
```

Use score as metric name, max as direction. All returned components are numeric. Obtain the real baseline score with the native verifier; no score is supplied here.

Prepare PRIVATE/baseline_attempt/final_model/model.json as the exact base_model.json bytes (optimizer_steps=0). Also write baseline_attempt/train_metrics.json with optimizer_steps=0 and baseline=true, baseline_attempt/README.md identifying an untrained baseline, and baseline_attempt/run.py as a simple stdlib script copying DATA_DIR/base_model.json to OUTPUT_DIR/final_model/model.json and writing the same zero-step metadata. This gives Finalizer complete baseline files if no candidate wins. A missing model path must fail; do not catch it and return an artificial score.

Finish Setup promptly after the frozen baseline gate passes. Never improve or replace judge code, inspect individual dev examples to engineer a candidate, or execute trial training during Setup.
