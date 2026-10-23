# Team update draft — not sent

Hi Han and Xintong, I expanded the Kali training pool to 156 source-reviewed examples and verified 32 independent utility-replay examples on Linux. Two frozen 128-step local 8B LoRA comparisons both scored 5/36 on domain dev and 54/72 on retention, versus 6/36 and 66/72 for the base, so I’m keeping the original checkpoint. Nautilus now works: I completed a real 20-step 8B QLoRA runtime check on one L4, verified adapter save/reload, and released the GPU; actual ABA integration and matched CUDA benchmark evaluation are next.

Code and evidence: https://github.com/Tobudase/aba-cyber-posttraining

This is a draft only; no email or Slack message was sent.
