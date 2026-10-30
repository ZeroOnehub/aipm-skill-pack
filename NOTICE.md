# 第三方声明

本仓库 `skills/` 下的 8 个 skill 都是自己写的。`project-initiation` 的 v2 借鉴了下表三个 MIT 项目的方法（文字改写，不是翻译），来源也写在该 skill 的「版本说明」和对应参考资料的开头。

| 位置 | 上游项目 | 借鉴了什么 | 许可证 | 版权 |
|---|---|---|---|---|
| `skills/project-initiation/references/事前验尸.md` | https://github.com/phuryn/pm-skills | `pre-mortem` 的风险分类与紧急度分级 | MIT | Copyright (c) 2026 Pawel Huryn |
| `skills/project-initiation/references/假设地图与验证实验.md` | https://github.com/phuryn/pm-skills ；https://github.com/caalvinz/opportunity-discovery-skill（`01087ae`） | 风险类型与「影响 × 风险」排序；判别性实验与预先承诺的判定标准 | MIT | Copyright (c) 2026 Pawel Huryn；Copyright (c) 2026 caalvinz |
| `skills/project-initiation/SKILL.md`（v2 新增的决策对象、一票否决、AI 程度判断等） | https://github.com/hope138/enterprise-ai-project-assessor（`e27a1e1`）；https://github.com/caalvinz/opportunity-discovery-skill | 企业 AI 项目评估的关卡与否决项；机会判断与决策记录 | MIT | Copyright (c) 2026 hope138；Copyright (c) 2026 caalvinz |

上游版本（借鉴时检出的提交）：phuryn/pm-skills `07b34f6`。

此前版本收录过 17 个改编自开源项目的工具 skill（PRD 审查、线框图、原型、系统提示词、评测、复盘等），已全部移除，由自己写的 `prd`、`prototype`、`tech-solution`、`model-eval`、`mvp-build`、`idea-canvas` 替代。需要查看那些改编内容和它们的许可证，见本仓库 git 历史中 `74a0e46` 及以前的提交。
