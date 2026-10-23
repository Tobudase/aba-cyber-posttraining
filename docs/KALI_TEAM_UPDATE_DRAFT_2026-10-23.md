# Team update draft — not sent

Hi Han and Xintong, I expanded the Kali training pool to 156source-reviewed examples and verified 32independent utility-replay examples plus four selected command semantics on Linux. I completed two frozen 128-step local 8B LoRA comparisons; both scored 5/36 on domain dev and 54/72 on retention, versus 6/36and 66/72 for the base, so I’m keeping the original checkpoint. Nautilus CPU jobs and a single A10 CUDA runtime check now work; full 8B GPU validation and actual ABA integration remain pending.

Code and evidence: https://github.com/Tobudase/aba-cyber-posttraining

This is a draft only; no email or Slack message was sent.
