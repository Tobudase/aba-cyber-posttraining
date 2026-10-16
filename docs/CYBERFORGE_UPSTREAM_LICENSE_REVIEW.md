# CyberForge 85 条可映射候选：上游源代码许可初筛

2026-10-16。对象是之前仅在**目录/元数据层**可对应到公开漏洞 ID 的 85 条候选（63 patch、22 poc-san），横跨 23 个项目。全部保持 `HOLD_NOT_TRAINING_APPROVED`。这次没有读取漏洞代码、教师正文或官方评测题，更没有生成训练集。

## 方法与结果

从固定 [CyberForge 项目包](https://huggingface.co/datasets/AmL-hug/cyberforge-projects) revision `02d0191c28d322bd22db6c97f8cb0688e7b1cdcd` 的 23 个压缩包，只读取 `project.json` 的 `main_repo_url` 与 `secure_base_commit`；每个压缩包 SHA256 与前次目录审核记录一致。随后按固定基础提交调用 [GitHub 的仓库 license API](https://docs.github.com/en/rest/licenses/licenses) 查询其可检测到的根目录许可文件，只保存 SPDX 识别结果、路径和固定提交链接，不保存许可正文。运行脚本：`scripts/audit-cyberforge-upstream-map.py` 和 `scripts/audit-cyberforge-upstream-licenses.py`。

| 初筛结果 | 项目 | 所涉候选记录 |
| --- | ---: | ---: |
| GitHub 根许可证被识别为具体 SPDX | 10 | 43 |
| 检测到根许可证，但 SPDX 为 `NOASSERTION` | 12 | 40 |
| 项目元数据没有可用 HTTPS 源仓库地址：`dnsmasq` | 1 | 2 |
| 合计 | 23 | 85 |

已识别的 10 个项目：`brotli`、`cgif`、`cjson`（MIT）；`double-conversion`、`pupnp`（BSD-3-Clause）；`freerdp`、`guetzli`（Apache-2.0）；`openh264`、`openjph`（BSD-2-Clause）；`open5gs`（AGPL-3.0）。这些只是 GitHub 在基础提交对根许可证文件的识别结果，不能推广到嵌套目录、第三方组件、轨迹文本或数据再利用权利。`NOASSERTION` 也不能解释为无许可证；需人工读实际文件。

完整来源映射与逐项目结果：`verification/cyberforge-linked-upstream-map.json`、`verification/cyberforge-linked-upstream-license-audit.json`。特别是 [CyberForge-projects 仓库的 MIT 许可](https://github.com/Cyb3rForge/CyberForge-projects)不能替代这些上游源代码与数据自身的条款；这个判断是对不同许可对象的区分，不是对项目权利的最终法律结论。

## 下一步门槛

1. 对 12 个 `NOASSERTION` 项目逐个读固定提交的实际许可文件；对 `dnsmasq` 找到官方源仓库和对应提交，确认其许可。
2. 核对 CyberForge 教师轨迹/项目包自身的具体数据许可和可用于模型训练的范围，不能仅凭上游代码仓库或数据集卡的概括字段推断。
3. 对每条候选补充成功/PoV 或补丁验证证据，以及与最终基准的漏洞/仓库/提交/fix-family 去重和任务格式一致性审核。**在此之前 85/85 条仍为 HOLD。**
