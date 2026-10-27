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
  ],
  "pending": [
    {
      "id": "D1",
      "kind": "decision",
      "stage": "initiation",
      "text": "第一版只做企业内部会议，还是也接外部客户会议？",
      "recommend": "只做内部：外部会议涉及客户授权，第一版绕开",
      "source": "01-立项/03-需求池.md",
      "status": "open"
    },
    {
      "id": "A1",
      "kind": "assumption",
      "stage": "initiation",
      "text": "用户愿意在会后 10 分钟内看纪要（目前只有 3 人访谈支持）",
      "recommend": "下周找 8 位行政同事试用两次会，看打开率",
      "source": "01-立项/05-MVP范围表.md",
      "status": "open"
    }
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
| `pending` | 否 | 待处理事项：等用户拍板的决定、待验证的假设、证据缺口、卡住的事。面板顶部「待处理」列表读它，见下文 |
| `build` | 否 | 研发交接以后才有：产品在开发文件夹里的位置。面板的「研发进度」卡读它，见下文 |

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

## 待处理事项（pending）

面板把 `pending` 里 `status` 不是 `resolved` 的项列在最上面，用户点「去处理」就把这件事放进输入框。面板还会自动把 `passed_pending`、`blocked` 的站和 `skipped` 的阶段列成待处理（显示站的 `note`），所以**这些不用重复写进 `pending`**，把 `note` 写清楚就行；`pending` 只放站状态表达不了的具体事项。

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | 是 | 项目内唯一：决定用 `D1`、`D2`……，假设用 `A1`……，证据缺口用 `G1`……，卡住用 `B1`…… |
| `kind` | 是 | `decision`（等用户拍板）/ `assumption`（待验证的假设）/ `gap`（缺证据）/ `blocked`（卡住） |
| `text` | 是 | 一句话说清是什么事，用户不打开文档也能看懂 |
| `stage` | 否 | 所属阶段 `id` |
| `recommend` | 否 | 决定类写推荐答案和一句理由；假设和缺口类写验证办法 |
| `source` | 否 | 详细讨论在哪份产出物，相对项目根目录的路径，面板上可以点开 |
| `status` | 否 | `open`（默认）或 `resolved` |
| `resolution` | 否 | 解决后写结论和日期，例如「选杭州（2026-10-21 用户拍板）」 |

规则：

- **决定类按决策卡写**：问题、选项、推荐、不选的后果。`text` 写问题，`recommend` 写推荐和理由，选项和后果写进 `source` 指向的文档。
- **同时开着的决定不超过 5 个**。多了说明在一次性甩问题，先挑会改变目标用户、范围、成本、安全、隐私的问，其余用默认值填上并写明理由。
- **用户回复后**：把该项改为 `resolved` 并写 `resolution`，再把结论落进对应产出物。已解决的项不删，留作决策记录，复盘时要用。
- 阶段 skill 只增改自己阶段的项（看 `stage`）；总控可以改任何项。

## 研发轨道（build）

研发交接时由 `build-launch` 写入（它的安装脚本会打印这一段），之后总控刷新 `stage` 和 `checked`：

```json
"build": {
  "path": "/Users/<你>/Documents/project/AI Workbench/开发/projects/会议纪要助手",
  "kit": "/Users/<你>/Documents/project/AI Workbench/开发",
  "name": "会议纪要助手",
  "tool": "Claude Code",
  "handoff": "2026-10-26",
  "synced": "2026-11-02",
  "stage": "2 后端 MVP（第 1 阶段）",
  "checked": "2026-11-03"
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `path` | 是 | 产品文件夹的**绝对路径**。面板直接读它下面的 `docs/项目状态.md` 和最新证据包 |
| `kit` | 是 | 开发文件夹（`AGENTS.md`、`verify.sh` 所在的那一层）的绝对路径 |
| `name` | 是 | 开发文件夹里的产品名，就是 `projects/` 下的文件夹名 |
| `tool` | 否 | 谁来写代码：Claude Code、Codex、Pi、研发团队…… |
| `handoff` / `synced` | 否 | 第一次交接、最近一次同步交接的日期 |
| `stage` / `checked` | 否 | 总控上次读到的研发阶段（`项目状态.md` 里「- 阶段：」那一行）和读的日期；面板读不到开发文件夹时显示它 |

## 写入规则

- 先读再整体写回，任何时候都要是合法 JSON（不要留注释和尾逗号）。
- 只改自己负责的部分：总控改 `currentStage`、阶段级 `status`，以及由总控编排的 03–06 阶段的 `stations`；阶段 skill（`project-initiation`、`prd`）改自己那一项的 `stations` 和 `note`；`pending` 按上一节的规则改。
- 阶段不必按顺序推进：可以有两个阶段同时是 `in_progress`（比如 PRD 写到一半先做 AI 可行性小样），`currentStage` 记用户主要在做的那个。
- 新接入一个阶段 skill 后，它第一次运行时把自己那一项从 `unavailable` 改为 `in_progress`，并写入 `stations`。
