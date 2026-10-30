# aipm.json 格式（version 2）

放在项目根目录 `<工作区>/<项目名>/aipm.json`。拾阶的右侧「项目」面板只读这个文件显示进度；产出物列表由面板直接扫描各节点目录得到，不需要写在这里。

## 完整示例

```json
{
  "version": 2,
  "project": "会议纪要助手",
  "type": "0→1",
  "created": "2026-10-30",
  "updated": "2026-11-12 21:30",
  "currentStage": "tech",
  "stages": [
    { "id": "initiation", "status": "done", "stations": [
      { "id": "01", "name": "把问题说清", "status": "passed" },
      { "id": "02", "name": "找到真用户", "status": "passed_pending", "note": "访谈样本只有 3 人" }
    ] },
    { "id": "prd", "status": "done" },
    { "id": "prototype", "status": "skipped", "note": "用户选择跳过：交互只有一个上传页" },
    { "id": "tech", "status": "in_progress", "stations": [
      { "id": "01", "name": "PRD 体检", "status": "passed" },
      { "id": "02", "name": "技术适配", "status": "in_progress" },
      { "id": "03", "name": "架构设计", "status": "not_started" },
      { "id": "04", "name": "评审定稿", "status": "not_started" }
    ] },
    { "id": "model-eval", "status": "not_started" },
    { "id": "mvp", "status": "not_started" }
  ],
  "pending": [
    {
      "id": "D1",
      "kind": "decision",
      "stage": "tech",
      "text": "第一版只给内部 5 位行政同事试用，还是对外开放？",
      "recommend": "只给内部：立项批的是 POC，先验证效果",
      "source": "04-技术方案/PRD补全清单.md",
      "status": "open"
    }
  ]
}
```

## 字段

| 字段 | 必填 | 说明 |
|---|---|---|
| `version` | 是 | 固定为 `2`。没有或为 `1` 的是老格式（老六阶段），见 [旧项目升级.md](旧项目升级.md) |
| `project` | 是 | 项目名，与文件夹名一致 |
| `type` | 否 | `0→1` 或 `1→N` |
| `created` / `updated` | 是 | `updated` 每次修改都要刷新 |
| `currentStage` | 是 | 用户主要在做的节点 `id` |
| `stages` | 是 | 六个节点，顺序固定，`id` 见下表 |
| `stages[].status` | 是 | 见状态表 |
| `stages[].note` | 否 | 一句话备注，面板悬停显示；`skipped` 时写跳过原因 |
| `stages[].stations` | 否 | 节点内各站，由节点 skill 自己写和维护 |
| `pending` | 否 | 待处理事项，见下文 |
| `build` | 否 | MVP 代码仓库的位置，由 `mvp-build` 写，见下文 |

节点 `id`、目录和各站（由各 skill 第一次运行时写入）：

| id | 目录 | 站 |
|---|---|---|
| `initiation` | `01-立项` | 01 把问题说清 / 02 找到真用户 / 03 收进需求池 / 04 看清对手 / 05 排出先后 / 06 拍板立项 |
| `prd` | `02-PRD` | 01 背景与目标 / 02 用户与旅程 / 03 功能清单 / 04 功能需求与交互 / 05 AI 设计 / 06 非功能、评测与定稿 |
| `prototype` | `03-原型交互` | 01 页面清单 / 02 线框图 / 03 可点击原型 / 04 走查回写 |
| `tech` | `04-技术方案` | 01 PRD 体检 / 02 技术适配 / 03 架构设计 / 04 评审定稿 |
| `model-eval` | `05-模型评测` | 01 定目标 / 02 候选模型调研 / 03 定标准 / 04 建评测集 / 05 跑评测 / 06 归因与报告 |
| `mvp` | `06-MVP` | 01 开发准备 / 02 后端 MVP / 03 前端风格 / 04 正式前端 / 05 联调验收 |

## 状态取值

| 层级 | 值 | 含义 |
|---|---|---|
| 节点 | `unavailable` | 该节点的 skill 未接入 |
| 节点 | `not_started` | 已接入，还没开始 |
| 节点 | `in_progress` | 进行中 |
| 节点 | `done` | 已完成 |
| 节点 | `skipped` | 用户选择跳过 |
| 站 | `not_started` / `in_progress` | 未开始 / 进行中 |
| 站 | `passed` | 过关 |
| 站 | `passed_pending` | 带「待验证」项通过 |
| 站 | `blocked` | 卡住，`note` 写卡在哪 |

## 待处理事项（pending）

面板把 `pending` 里 `status` 不是 `resolved` 的项列在最上面，用户点「去处理」就把这件事放进输入框。面板还会自动把 `passed_pending`、`blocked` 的站和 `skipped` 的节点列成待处理（显示 `note`），所以**这些不用重复写进 `pending`**，把 `note` 写清楚就行。

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | 是 | 项目内唯一：决定 `D1`……，假设 `A1`……，证据缺口 `G1`……，卡住 `B1`…… |
| `kind` | 是 | `decision`（等用户拍板）/ `assumption`（待验证的假设）/ `gap`（缺证据、上游改了下游没跟）/ `blocked`（卡住） |
| `text` | 是 | 一句话说清是什么事，用户不打开文档也能看懂 |
| `stage` | 否 | 所属节点 `id` |
| `recommend` | 否 | 决定类写推荐答案和一句理由；假设和缺口类写验证办法 |
| `source` | 否 | 详细讨论在哪份产出物，相对项目根目录的路径，面板上可以点开 |
| `status` | 否 | `open`（默认）或 `resolved` |
| `resolution` | 否 | 解决后写结论和日期 |

规则：

- **决定类按决策卡写**：问题、选项、推荐、不选的后果。`text` 写问题，`recommend` 写推荐和理由，选项和后果写进 `source` 指向的文档。
- **同时开着的决定不超过 5 个**。
- 用户回复后改为 `resolved` 并写 `resolution`，再把结论落进对应产出物。已解决的项不删，留作决策记录。
- 节点 skill 只增改自己节点的项（看 `stage`）；总控可以改任何项。

## MVP 代码仓库（build）

由 `mvp-build` 的安装脚本写入，之后总控和 `mvp-build` 刷新 `stage`、`checked`：

```json
"build": {
  "path": "/Users/<你>/Documents/拾阶工作区/会议纪要助手/06-MVP/app",
  "name": "会议纪要助手",
  "tool": "拾阶",
  "handoff": "2026-11-15",
  "synced": "2026-11-20",
  "stage": "1 后端 MVP（第 2 期）",
  "checked": "2026-11-21"
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `path` | 是 | 代码仓库的**绝对路径**（`AGENTS.md`、`verify.sh` 所在那一层）。面板直接读它下面的 `docs/项目状态.md` 和最新证据包 |
| `name` | 否 | 产品名 |
| `tool` | 否 | 谁写代码：拾阶、Claude Code、Codex、研发团队…… |
| `handoff` / `synced` | 否 | 第一次安装、最近一次同步的日期 |
| `stage` / `checked` | 否 | 上次读到的「- 阶段：」一行原文和读的日期；面板读不到代码仓库时显示它 |

代码仓库的阶段：0 开发准备、1 后端 MVP、2 前端风格、3 正式前端、4 联调验收、5 上线（可选）。

## 写入规则

- 先读再整体写回，任何时候都要是合法 JSON（不要留注释和尾逗号）。
- 只改自己负责的部分：总控改 `currentStage`、节点级 `status`；节点 skill 改自己那一项的 `stations` 和 `note`；`pending` 按上一节的规则改；`build` 由 `mvp-build` 写。
- 节点不必按顺序推进，可以有两个节点同时是 `in_progress`。
- 节点 skill 第一次运行时把自己那一项从 `unavailable` 或 `not_started` 改为 `in_progress`，并写入 `stations`。
