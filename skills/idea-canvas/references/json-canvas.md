# JSON Canvas 格式要点

拾阶的画布用开放的 JSON Canvas 1.0 格式（jsoncanvas.org），扩展名 `.canvas`。整个文件是一个 JSON 对象：

```json
{
  "nodes": [
    {"id": "n1", "type": "text", "text": "随手的观点，支持 Markdown", "x": 0, "y": 0, "width": 260, "height": 140},
    {"id": "n2", "type": "link", "url": "https://example.com/article", "x": 300, "y": 0, "width": 300, "height": 120},
    {"id": "n3", "type": "file", "file": "灵感画布/灵感画布-文档/脑暴.md", "x": 0, "y": 200, "width": 300, "height": 220},
    {"id": "g1", "type": "group", "label": "问题", "x": -40, "y": -60, "width": 700, "height": 520, "color": "1"}
  ],
  "edges": [
    {"id": "e1", "fromNode": "n1", "toNode": "n2", "label": "参考"}
  ]
}
```

## 节点

| 字段 | 说明 |
|---|---|
| `id` | 唯一编号。拾阶新建的节点用随机串；AI 整理加的以 `ai-` 开头 |
| `type` | `text` / `file` / `link` / `group` |
| `x` `y` `width` `height` | 位置和大小，整数，单位像素；`y` 向下为正 |
| `color` | 可省。`"1"` 红、`"2"` 橙、`"3"` 黄、`"4"` 绿、`"5"` 青、`"6"` 紫，或 `#RRGGBB` |
| `text` | `text` 节点的内容，Markdown |
| `file` | `file` 节点的文件路径，**相对于工作区根目录**（和 Obsidian 把工作区当库打开时一致） |
| `url` | `link` 节点的网址 |
| `label` | `group` 节点的标题 |

- **分组是按位置算的**：节点的矩形完全落在分组矩形里，就算在这个组里。移动分组时要连同里面的节点一起移动。
- 数组顺序就是叠放顺序，后面的在上层：分组要排在它里面的节点前面。

## 连线

| 字段 | 说明 |
|---|---|
| `id` | 唯一编号 |
| `fromNode` / `toNode` | 两端的节点编号 |
| `fromSide` / `toSide` | 可省。`top` / `right` / `bottom` / `left` |
| `toEnd` | 可省，默认 `arrow`；`none` 为无箭头 |
| `label` | 可省，连线上的文字 |

## 拾阶的约定

- 画布里粘贴的图片存在画布旁边的 `images/` 文件夹里，用 `file` 节点引用。
- 「新建文档」节点会在 `<画布名>-文档/` 下建一个 Markdown 文件，用 `file` 节点引用；双击打开编辑器。
- 直接改文件时保证始终是合法 JSON；拾阶的画布标签页发现文件变了会自动重新加载（用户正在编辑时会提示）。
