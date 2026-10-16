# External training data review (2026-10-16)

CyberGym's official 1,507 tasks are reserved for evaluation in this project. External data is not automatically independent just because task IDs differ.

We reviewed the public [CyberForge project collection](https://huggingface.co/datasets/AmL-hug/cyberforge-projects) and the pinned [Gemma teacher trajectories](https://huggingface.co/datasets/AmL-hug/cyberforge-teacher-traj-gemma4-31b) at revision `818851c1d8834b9e234f602e67268fc82a915755`. The project collection describes 100 OSS-Fuzz projects and injected vulnerabilities. Its public GitHub root directory listing was pinned at `9e09f4981a5a1a2bc99bd9a6f2b6788a994a5870` for a project-name comparison with the locked CyberGym task index.

| Metadata check | Result |
| --- | ---: |
| CyberForge project directories | 100 |
| Project names exactly matching an official CyberGym project name | 62 |
| Official CyberGym tasks under those names | 875 |
| Gemma teacher trajectory records | 880 |
| Records from same-name projects | 498 |
| Records from 27 projects without exact name matches | 382 |
| Of those 382, `poc-san` / patch task modes | 92 / 290 |
| Exact canonical repository URL matches among the 27 projects | 0 |
| Records approved for training | **0** |

Only the dataset's `metadata` fields were used for this audit. Exact project-name or repository-URL comparison is a screening step, not proof of separate vulnerability origin. The 382 records remain on hold until source repository aliases/forks, base and fix commits, injection provenance, source licenses, and task/harness compatibility are reviewed. The trajectory metadata file also lacks a per-record verification status; the publisher's description of successful trajectories was not independently reproduced here. No CyberForge raw messages, patches or model outputs are included in this repository.

Other sources considered: [CyberRepo-10K](https://huggingface.co/datasets/WhitzardAgent/CyberRepo-10K) is gated for academic use and mixes OSS-Fuzz/OSV sources, so it needs access and overlap review before any training use. [SI2CA](https://huggingface.co/datasets/Self-Improving-Coding-Agents/SI2CA-Training-Trajectories) offers general coding-agent trajectories rather than cybersecurity tasks; [CABRA](https://huggingface.co/datasets/microsoft/CABRA) is a synthetic code-understanding dataset. Neither is treated as CyberGym-domain training data in this project.
