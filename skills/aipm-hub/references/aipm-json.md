# aipm.json 格式

放在项目根目录 `<工作区>/<项目名>/aipm.json`。拾阶的右侧「项目」面板只读这个文件显示进度；产出物列表由面板直接扫描各阶段目录得到，不需要写在这里。

## 完整示例

```json
{
  "version": 1,
  "project": "会议纪要助手",
  "type": "0→1",
  "created": "2026-10-07",
  "updated": "2026-10-07 21:30",
  "currentStage": "initiation",
  "stages": [
    {
      "id": "initiation",
      "status": "in_progress",
      "note": "",
      "stations": [
        { "id": "01", "name": "把问题说清", "status": "passed" },
        { "id": "02", "name": "找到真用户", "status": "passed_pending", "note": "访谈样本只有 3 人" },
        { "id": "03", "name": "收进需求池", "status": "in_progress" },
        { "id": "04", "name": "看清对手", "status": "not_started" },
        { "id": "05", "name": "排出先后", "status": "not_started" },
        { "id": "06", "name": "拍板立项", "status": "not_started" }
      ]
    },
    { "id": "prd", "status": "unavailable" },
    { "id": "prototype", "status": "unavailable" },
    { "id": "ai-design", "status": "unavailable" },
    { "id": "evaluation", "status": "unavailable" },
    { "id": "launch-review", "status": "unavailable" }
  ]
}
```

## 字段

| 字段 | 必填 | 说明 |
|---|---|---|
| `version` | 是 | 固定为 `1` |
| `project` | 是 | 项目名，与文件夹名一致 |
| `type` | 否 | `0→1` 或 `1→N` |
| `created` / `updated` | 是 | `updated` 每次修改都要刷新 |
| `currentStage` | 是 | 当前阶段的 `id` |
| `stages` | 是 | 六个阶段，顺序固定，`id` 见下表 |
| `stages[].status` | 是 | 见下方状态表 |
| `stages[].note` | 否 | 一句话备注，面板悬停显示 |
| `stages[].stations` | 否 | 阶段内各站，由阶段 skill 自己定义和维护 |

阶段 `id` 与目录：`initiation`→`01-立项`、`prd`→`02-PRD`、`prototype`→`03-原型交互`、`ai-design`→`04-AI方案设计`、`evaluation`→`05-评测`、`launch-review`→`06-上线复盘`。

## 状态取值

| 层级 | 值 | 含义 |
|---|---|---|
| 阶段 | `unavailable` | 该阶段 skill 未接入 |
| 阶段 | `not_started` | 已接入，还没开始 |
| 阶段 | `in_progress` | 进行中 |
| 阶段 | `done` | 已完成 |
| 阶段 | `skipped` | 用户选择跳过 |
| 站 | `not_started` / `in_progress` | 未开始 / 进行中 |
| 站 | `passed` | 过关卡 |
| 站 | `passed_pending` | 带「待验证」项通过 |
| 站 | `blocked` | 卡住，`note` 写卡在哪 |

## 写入规则

- 先读再整体写回，任何时候都要是合法 JSON（不要留注释和尾逗号）。
- 只改自己负责的部分：总控改 `currentStage`、阶段级 `status`，以及由总控编排的 03–06 阶段的 `stations`；阶段 skill（`project-initiation`、`prd`）改自己那一项的 `stations` 和 `note`。
- 新接入一个阶段 skill 后，它第一次运行时把自己那一项从 `unavailable` 改为 `in_progress`，并写入 `stations`。
