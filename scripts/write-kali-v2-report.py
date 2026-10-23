"""Write report only after both frozen arms have complete verified comparisons."""
import json
from pathlib import Path
from benchkit import ROOT,write_json

def main():
 root=ROOT/'docs/verification/kali-replay-v2';r=json.loads((root/'comparison.json').read_text())
 if r['status']!='TWO_FROZEN_ARMS_COMPLETE':raise ValueError('Both arms must finish first')
 a,b=[r['arms'][x] for x in ['domain_control','domain_plus_replay']]
 d=lambda x:x['comparisons']['domain'];t=lambda x:x['comparisons']['retention']
 counts=lambda x,k:str(int(x['comparisons'][k]['post_correct']))
 adopted=[name for name,arm in r['arms'].items() if arm['fixed_rule_passed']]
 conclusion='Keep the original base; neither adapter passes the frozen acceptance rule.' if not adopted else 'Candidate passes the development rule: '+', '.join(adopted)+'. Independent validation is still required; do not claim official performance.'
 text=f'''# KaliBench second-round ablation and Linux validation — October 23, 2026

{conclusion}

## Completed data and semantic work

- Domain training pool:156rows/80correlated intent families, expanded from108rows/55families. Six proposed overlapping operation families were excluded before training. Query/command exact and protected operation-signature overlap remain zero; this does not prove semantic or pretraining independence.
- Independent-source general utility replay:32authored records/16families grounded in pinned GNU Coreutils documentation. All32 executable fixtures passed onLinux. Replay tools do not overlap the authored development/confirmation tool names. The rows retain their creation-time quality label; later Linux verification is in the separate hash-linked receipt.
- Mandatory per-tool option coverage improved:34/36domain queries had missing flags inV1, versus12/36withV2 (also12/36in the selected96-row domain core). This is lexical coverage, not evidence of learning or comprehensive tool coverage.
- Four fixed Linux fixture checks passed: tshark quiet mode suppresses packet output; editcap retains the selected packet range; YARA expects rules before target; netstat accepts the unique long-option abbreviation in this installed version. `pescan` exists and `pe-scan` does not in the installed package; that executable-name check is not fullPE semantic validation.
- Linux package versions differ from the pinned upstream Kali help snapshots. Native gold and scorer were not changed; no additional matches were silently credited.

## Frozen matched experiment

Original RedSage-K-SFT-GRPO8B revision843e2e3096e7de68f5c35eb16238f4909f21695a, local MLX affine4/group64, AppleM2Pro16GiB. Each arm starts from the same original base. Same LoRA(last4layers,q/v,rank8,scale2), LR1e-5, batch1, seed42, assistant-only final-answer supervision, greedy1024-token evaluation without tool help.

Both arms have128optimizer steps. The shared core contains96rows covering all80domain families. Control adds32repeated domain presentations; treatment replaces those32presentations with the independent utility replay. This equal-step comparison does **not** equalize token/FLOP budgets or total domain exposure, and cannot isolate a pure added-data effect. The two arm protocols and runner hashes were frozen before either run. No third candidate was tried based on these results.

| Same exposed development | Original base | Domain control | Domain + replay |
| --- | ---: | ---: | ---: |
| Domain Exact / option diagnostic |6/36|{counts(a,'domain')}/36|{counts(b,'domain')}/36|
| Domain native Total |73.41|{d(a)['post_native']['total_score']:.2f}|{d(b)['post_native']['total_score']:.2f}|
| CLI retention Exact / option diagnostic |66/72|{counts(a,'retention')}/72|{counts(b,'retention')}/72|
| Retention native Total |97.22|{t(a)['post_native']['total_score']:.2f}|{t(b)['post_native']['total_score']:.2f}|
| Frozen rule passed |baseline|{a['fixed_rule_passed']}|{b['fixed_rule_passed']}|

The original72CLI rows have repeated template variants; individual rows are not independent skills. The36domain rows are source-silver and already exposed during diagnosis. No statistical significance, full-benchmark generalization or independent label-review claim is made. The fixed rule requires improved domain Exact and option matching, nondecreasing domainTotal and retention, and no runtime/truncation/XML failures.

## Interpretation and remaining work

Compare both arms to the original base and disclose failures. A reduction in regression relative to the domain control would not by itself justify promotion if the base is still better. Better data coverage has not automatically established successful adaptation. Whole-domain semantic validation, fresh held-out development, multi-seed confirmation and actual ABA-controlled training/evaluation remain separate tasks. New confirmation bodies and official tests remain unqueried.

This round is **manual SFT**, not actualABA. A train-only128-row Linux worker package is prepared and checked; the CUDA recipe(NF4/rank16/allq-v layers) differs from MLX, so it requires its own matched baseline/protocol. The realABA controller, private evaluator isolation and controlled submission need end-to-end validation before search is enabled.

## Evidence and score replay

- `verification/kali-replay-v2/comparison.json`: both arms and predeclared decision.
- `verification/kali-replay-v2/<arm>/`: exact executed runner/protocol, raw predictions, scores and training receipts. Tensors are private.
- `verification/kali-v2-option-coverage.json`: descriptive flag coverage.
- `verification/kali-linux-semantics-2026-10-23.json` and `kali-replay-fixtures-2026-10-23.json`: actual Linux execution evidence.
- `configs/kali-replay-v2-*.protocol.json`: frozen protocol hashes, protected-data commitments, budgets.
- After restoring the pinned sources: `python scripts/analyze-kali-replay-ablation-v2.py` recomputes public scores. `--verify-local-adapters` additionally checks private tensors and only works in the original workspace.
- Original workspace:42tests passed with its audit dependencies; curated public suite is checked separately. Recorded GPU/runtime progress is in the accompanying resource report.
'''
 (ROOT/'docs/KALI_REPLAY_ABLATION_REPORT_2026-10-23.md').write_text(text)
 print(conclusion)
if __name__=='__main__':main()
