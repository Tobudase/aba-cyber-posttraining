# CUDA baseline and native ABA preparation — October 23, 2026

The next CUDA baseline could not start because the normal scheduler found no
suitable resources. **This round produced no CUDA predictions, optimizer updates,
model API calls or native ABA controller run.** The earlier successful20-step
8B L4 smoke and negative Mac experiments remain separate evidence.

## Completed preparation

- Frozen separate CUDA protocol: RedSage-K-SFT-GRPO at the pinned official
  revision, NF4/BF16, all-layer q/v LoRA rank16/alpha32,128 TRAIN-only AdamW
  updates at1e-5, batch1/seed42. Inference uses aligned prefix, greedy decoding,
  max256 output tokens,36 exposed domain-dev plus72 exposed retention examples.
  There is no help-doc augmentation. This differs from the Mac protocol and
  does not reproduce official BF16/8192-token evaluation.
- All128 training supervision boundaries and108 inference prompt hashes were
  checked with the pinned native tokenizer. GPU inference receives only IDs,
  messages, set names and prompt hashes; labels/scoring stay on the host.
- CPU-only job packed the verified Linux dependencies into one295,516,160-byte
  archive, SHA256 `c47d41129fdb9e25d874b5bae9e69010f323cf65850fffa98ab5e53341e746dd`.
  CPU packing took109.53seconds. This avoids copying thousands of individual
  files, but its GPU staging speed benefit is **not measured yet**.
- Prepared a controlled host worker: one GPU at a time, finite1800-second Job,
  matched CPU/RAM/scratch requests and limits, no service-account token,
  ordinary scheduling, bounded360-second Pending wait, receipt/prediction
  hashes, and collection/cleanup. No agent-supplied shell, paths, data or
  hyperparameters are accepted by the bridge.
- Created a native ABA task using128 frozen TRAIN examples and the fixed client.
  The private evaluator receives only aggregate host scores, with the existing
  all-or-nothing improvement/retention/format adoption rule. A baseline scores0;
  a candidate scores+1 only if every rule passes, otherwise-1. This protects the
  original base from forced promotion. Adapter pointers must match the evaluated
  persistent adapter SHA; no model tensors are redistributed.
- On the owned Ubuntu CPU VM, the actual installed ABA `AgentConfig` validated
  this task. Its pinned native bwrap emitter reached the host health endpoint
  over an SSH loopback forward, without changing the emitter or disabling
  sandboxing. This is **configuration/connectivity preflight**, not a complete
  ABA role-policy/worker/scorer run. The task is retained on the VM's persistent
  disk. No development questions/labels were transferred with the task.
-48 local unit tests pass, including six new allocation/input-boundary checks.
  Hardware execution and full native ABA verification remain pending.

## Actual scheduling attempts and cleanup

The global `reached-quota` limit is now200pods, and ordinary Jobs were admitted.
The priority-specific pods=0 quotas still exist; no priority changes were made.

1. Original proven L4 hostname: Pending, no GPU allocation; removed.
2. Broader normal L4 selector: Pending due GPU/memory availability; removed.
3. A10 selector: all24 samples remained Pending; removed after360-second
   scheduling bound (373.86seconds host lifecycle including cleanup).

The A10 hardware-only protocol revision was made **before any model execution**.
Its previous L4 protocol is preserved in
`configs/kali-cuda-cycle-v1.preallocation-L4.json`. No model scores informed the
change; data, training and decoding settings stayed fixed.

The final scheduler message included `Insufficient nvidia.com/gpu` and
`Insufficient memory`; many other nodes did not match hardware requirements or
had reservations/taints. Those counts describe the cluster scheduler's filters,
not personal quota exhaustion or a claim that every cluster GPU is unavailable.
No reservation tolerations, node binding, quota changes or preemption changes
were introduced. A direct node-health get was RBAC-denied; it was not bypassed.

Verified cleanup: zero cycle Jobs/Pods/ConfigMaps, VM Stopped/Halted,32GiB model
cache PVC Bound. CPU packing Job and loopback broker were stopped/deleted too.
Other users' resources were not changed.

## Next executable step

Review the frozen protocol and copy `configs/kali-cuda-jobs.example.json` to
`configs/kali-cuda-jobs.local.json`, filling only your own approved namespace and
prepared cache claim. The current private setup already exists for this user.
It requires the previously verified pinned model cache and dependency archive;
this example does not create or approve them.

Run the finite E0 baseline once suitable A10 resources are available:

```sh
PYTHONPATH=.tools/athena-audit-deps .tools/cti-faith-venv/bin/python \
  scripts/kali_cuda_jobs.py --run-id E0 --phase infer
```

An unscheduled attempt is archived on the next retry; a prior allocated/failed
run requires review rather than silently rerunning training. A successful
baseline needs the worker receipt, collected predictions, recomputed scores and
host `verified.json`, not just Job creation.

After E0 succeeds, start the owned CPU VM only when ready to use it, wait for SSH,
check the retained task hashes, then execute `scripts/run-kali-aba-cuda.py` with
the local Python environment above. It starts a transient loopback broker and
runs the native ABA controller through SSH. It reads the existing private token
without printing it; the user's password/token must never be pasted into chat.
The command refuses to call the model API if a matching E0 is missing.

ABA is limited to **one fixed-recipe E2 candidate** for this initial connection
check. E1 is an optional fixed manual control, not executed this round. E2 uses
the same frozen recipe for engineering parity, not autonomous data generation,
hyperparameter discovery, or a claim of RSI performance. No adapter is adopted
until the frozen rule and independent native journal/artifact checks pass.

After any native run, collect its journal and exact executed client, receipts,
selected pointer and declaration; verify the real adapter/prediction provenance.
Then remove only that run's private launch credential state, stop sidecars,
close the broker and halt the VM. The controller/service have45-minute limits;
GPU Jobs have their own hard deadlines; the VM retains its90-minute auto-stop.
These are safeguards, not a substitute for checking cleanup.

New12-example domain confirmation and all official tests remain disabled and
unqueried. Exposed source-silver development results cannot establish official
ranking, independent generalization or expert-validated security capability.

Evidence: `verification/kali-cuda-aba-preflight.json`,
`verification/kali-cuda-runtime-archive.json`, and
`verification/kali-cuda-cycle-v1/{scheduling-latest,cleanup}.json`.
