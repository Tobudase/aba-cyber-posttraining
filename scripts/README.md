# Code and experimental materials

[Project overview](../README.md) · [Score reproduction](../docs/REPRODUCTION.md) · [Results by question](../results/README.md)

The most recent studies keep their score checks and plotting scripts **beside their result records**. This directory also contains dated scripts for the earlier studies. Start with the experiment whose inputs and outcome you want to inspect.

| Purpose | Code or configuration | Associated evidence |
| --- | --- | --- |
| Recount the teacher comparison and redraw its figures | [Score verifier](../results/teacher-transfer-2026-11-23/verify.py) · [Figure source](../results/teacher-transfer-2026-11-23/figures.py) | [Second single-example study](../results/teacher-transfer-2026-11-23/RESULT_ZH.md) |
| Check how output format affected transfer | [Paired score recount](../results/constraint-audit-2026-11-23/recount.py) | [Strict and recoverable outcomes](../results/constraint-audit-2026-11-23/RESULT_ZH.md) |
| Inspect the earlier teacher SFT implementation | [Pinned training and evaluation snapshots](../code-snapshots/teacher-sft-20261117/README.md) | [Audited teacher study](../results/kali-verified-teacher-stage-2026-11-17/) |
| Check the Qwen fixed-SFT development result | [Confirmation verifier](verify-kali-qwen-confirmation-public.py) · [Figure source](plot-kali-qwen-confirmation.py) | [87-example internal confirmation](../results/kali-qwen-confirmation-2026-10-28/) |
| Inspect tests for ABA and evaluation | [Test suite](../tests/) · [Upstream compatibility patches](../patches/) | [Native ABA result and dependencies](../results/kali-qwen-native-aba-2026-11-15/RESULT_ZH.md) |
| Trace early benchmark preparation | [Scorer audit](audit-benchkit-scorers.py) · [Model and runtime locks](../configs/) | [Verification records](../docs/verification/) |

For data provenance, consult the [data manifests](../data/manifests/), [authored fixtures and pilot data](../data/benchkit/) and [source notices](../NOTICE.md). The [synthetic ABA example](../examples/aba-bigram/) and [tiny CTI pilot adapter](../artifacts/cti-source-pilot-tiny-adapter/) belong to the initial integration checks.
