# 第三方声明

本仓库 `skills/` 下除 `aipm-hub`、`project-initiation` 两个原创 skill 外，其余内容改编自以下开源项目；`project-initiation/references/` 里的两份方法说明借鉴了下表最后两行的方法（改写，不是翻译）。每个 skill 目录内附有对应上游的许可证原文；Apache-2.0 项目的改编文件已在文件开头注明「相对原文有修改」。

| 目录 | 上游项目 | 上游文件 | 许可证 | 版权 |
|---|---|---|---|---|
| `skills/interview-script` | https://github.com/phuryn/pm-skills | `pm-product-discovery/skills/interview-script` | MIT | Copyright (c) 2026 Pawel Huryn |
| `skills/retro` | https://github.com/phuryn/pm-skills | `pm-execution/skills/retro` | MIT | Copyright (c) 2026 Pawel Huryn |
| `skills/prd` | https://github.com/phuryn/pm-skills | `pm-execution/skills/create-prd` | MIT | Copyright (c) 2026 Pawel Huryn |
| `skills/prd` | https://github.com/anthropics/knowledge-work-plugins | `product-management/skills/write-spec` | Apache-2.0 | Anthropic |
| `skills/research-synthesis` | https://github.com/anthropics/knowledge-work-plugins | `product-management/skills/synthesize-research` | Apache-2.0 | Anthropic |
| `skills/metrics-review` | https://github.com/anthropics/knowledge-work-plugins | `product-management/skills/metrics-review` | Apache-2.0 | Anthropic |
| `skills/prd-review` | https://github.com/pmYangKun/check-prd-skill | 全部 `SKILL.md` 与 `references/` | Apache-2.0 | Copyright 2026 杨堃 (pmYangKun)；方法论来源：《决胜B端（第二版）》《决胜体验设计》。原 NOTICE 保留在该目录 |
| `skills/html-wireframe` | https://github.com/plannotator/effective-html | `skills/html-wireframe` | MIT | Copyright (c) 2026 plannotator |
| `skills/html-prototype` | https://github.com/plannotator/effective-html | `skills/html-prototype` | MIT | Copyright (c) 2026 plannotator |
| `skills/harness-patterns` | https://github.com/keli-wen/agentic-harness-patterns-skill | `skills/agentic-harness-patterns-zh` | MIT | 见该目录 LICENSE |
| `skills/system-prompt-design` | https://github.com/kangarooking/system-prompt-skills | 15 个模式 `*/SKILL.md`（放在 `references/`） | MIT | 见该目录 LICENSE |
| `skills/eval-error-analysis` | https://github.com/hamelsmu/evals-skills | `skills/error-analysis` | MIT | Copyright (c) 2026 Hamel Husain |
| `skills/eval-synthetic-data` | https://github.com/hamelsmu/evals-skills | `skills/generate-synthetic-data` | MIT | Copyright (c) 2026 Hamel Husain |
| `skills/eval-judge-prompt` | https://github.com/hamelsmu/evals-skills | `skills/write-judge-prompt` | MIT | Copyright (c) 2026 Hamel Husain |
| `skills/eval-validate-judge` | https://github.com/hamelsmu/evals-skills | `skills/validate-evaluator` | MIT | Copyright (c) 2026 Hamel Husain |
| `skills/eval-rag` | https://github.com/hamelsmu/evals-skills | `skills/evaluate-rag` | MIT | Copyright (c) 2026 Hamel Husain |
| `skills/eval-audit` | https://github.com/hamelsmu/evals-skills | `skills/eval-audit` | MIT | Copyright (c) 2026 Hamel Husain |
| `skills/eval-review-ui` | https://github.com/hamelsmu/evals-skills | `skills/build-review-interface` | MIT | Copyright (c) 2026 Hamel Husain |
| `skills/project-initiation/references/事前验尸.md` | https://github.com/phuryn/pm-skills | `pre-mortem` 的风险分类与紧急度分级（方法借鉴，文字改写） | MIT | Copyright (c) 2026 Pawel Huryn |
| `skills/project-initiation/references/假设地图与验证实验.md` | https://github.com/phuryn/pm-skills ；https://github.com/caalvinz/opportunity-discovery-skill（`01087ae`） | 风险类型与「影响 × 风险」排序；判别性实验与预先承诺的判定标准（方法借鉴，文字改写） | MIT | Copyright (c) 2026 Pawel Huryn；Copyright (c) 2026 caalvinz |

上游版本（改编时检出的提交）：phuryn/pm-skills `07b34f6`、anthropics/knowledge-work-plugins `a266ab8`、pmYangKun/check-prd-skill `505b572`、plannotator/effective-html `975b047`、keli-wen/agentic-harness-patterns-skill `17549f5`、kangarooking/system-prompt-skills `252cd52`、hamelsmu/evals-skills `22418da`。
