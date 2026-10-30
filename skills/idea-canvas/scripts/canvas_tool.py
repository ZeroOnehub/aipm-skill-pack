#!/usr/bin/env python3
"""灵感画布（JSON Canvas 格式的 .canvas 文件）的读和整理。

用法：
    python3 canvas_tool.py summary <画布.canvas> [--workspace <工作区根目录>]
    python3 canvas_tool.py apply <画布.canvas> <整理方案.json>

summary：列出全部节点（编号、类型、所在分组、文字或链接或文件）和连线，给 AI 读。
    --workspace 给了时，文档节点会附上文件开头几行。
apply：按整理方案把节点排进分组，写回画布。
    - 第一次整理前把原文件备份为 <画布名>.整理前.canvas（已有备份不覆盖）。
    - 用户的节点一个不删、编号不变、文字不改，只移动位置；用户的连线全部保留。
    - AI 加的分组、主题小结、总览节点编号都以 ai- 开头；再次整理时先清掉上一次的 ai- 节点。
    - 方案里没提到的用户节点放进「未归类」分组；用户原来的分组没被方案沿用的，会被去掉（备份里还在）。

整理方案 JSON：
{
  "overview": "放在最上面的一段总览（Markdown）",
  "groups": [
    {"label": "主题名", "summary": "这个主题的两三句小结", "nodes": ["节点编号", ...], "color": "4", "reuse": "沿用的用户分组编号（可省）"}
  ]
}
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

GAP = 40          # 节点之间
PAD = 40          # 分组内边距
HEADER = 60       # 分组标题留白
GROUP_GAP = 120   # 分组之间
COLUMNS = 2       # 分组内每行几个节点
GROUPS_PER_ROW = 3
SUMMARY_H = 120
OVERVIEW_W = 720
OVERVIEW_H = 200
DEFAULT_W, DEFAULT_H = 260, 140


def load(path: Path) -> dict:
    text = path.read_text(encoding="utf-8").strip()
    data = json.loads(text) if text else {}
    data.setdefault("nodes", [])
    data.setdefault("edges", [])
    return data


def save(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent="\t") + "\n", encoding="utf-8")


def size(node: dict) -> tuple[int, int]:
    return int(node.get("width") or DEFAULT_W), int(node.get("height") or DEFAULT_H)


def inside(node: dict, group: dict) -> bool:
    w, h = size(node)
    gw, gh = size(group)
    return (group["x"] <= node["x"] and group["y"] <= node["y"]
            and node["x"] + w <= group["x"] + gw and node["y"] + h <= group["y"] + gh)


def summary(path: Path, workspace: Path | None) -> None:
    data = load(path)
    groups = [n for n in data["nodes"] if n.get("type") == "group"]
    print(f"# 画布：{path.name}\n\n共 {len(data['nodes'])} 个节点（其中分组 {len(groups)} 个），{len(data['edges'])} 条连线。\n")
    for g in groups:
        print(f"- 分组 `{g['id']}`：{g.get('label', '（无标题）')}")
    print()
    for n in data["nodes"]:
        kind = n.get("type")
        if kind == "group":
            continue
        where = [g.get("label", g["id"]) for g in groups if inside(n, g)]
        head = f"## `{n['id']}` {kind}" + (f"（在分组：{'、'.join(where)}）" if where else "") + (" [AI 加的]" if n["id"].startswith("ai-") else "")
        print(head)
        if kind == "text":
            print(n.get("text", "").strip() or "（空）")
        elif kind == "link":
            print(f"链接：{n.get('url', '')}")
        elif kind == "file":
            print(f"文件：{n.get('file', '')}")
            if workspace is not None:
                f = workspace / n.get("file", "")
                if f.is_file() and f.suffix.lower() in (".md", ".markdown", ".txt"):
                    lines = f.read_text(encoding="utf-8", errors="replace").splitlines()[:12]
                    print("> " + "\n> ".join(line for line in lines if line.strip()))
        print()
    if data["edges"]:
        print("## 连线\n")
        for e in data["edges"]:
            label = f"「{e['label']}」" if e.get("label") else ""
            print(f"- `{e['fromNode']}` → `{e['toNode']}` {label}")


def apply(path: Path, plan_path: Path) -> None:
    data = load(path)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    backup = path.with_name(path.stem + ".整理前.canvas")
    if not backup.exists():
        shutil.copy2(path, backup)

    nodes = [n for n in data["nodes"] if not str(n["id"]).startswith("ai-")]
    by_id = {n["id"]: n for n in nodes}
    user_groups = {n["id"]: n for n in nodes if n.get("type") == "group"}
    items = [n for n in nodes if n.get("type") != "group"]

    seen: set[str] = set()
    problems: list[str] = []
    plan_groups = plan.get("groups", [])
    for g in plan_groups:
        for nid in g.get("nodes", []):
            if nid not in by_id or by_id[nid].get("type") == "group":
                problems.append(f"方案里的节点 {nid} 不存在或是分组")
            elif nid in seen:
                problems.append(f"节点 {nid} 出现在两个分组里")
            seen.add(nid)
        if g.get("reuse") and g["reuse"] not in user_groups:
            problems.append(f"沿用的分组 {g['reuse']} 不存在")
    if problems:
        raise SystemExit("整理方案有问题，没有写入：\n- " + "\n- ".join(problems))
    leftover = [n["id"] for n in items if n["id"] not in seen]
    if leftover:
        plan_groups = plan_groups + [{"label": "未归类", "summary": "", "nodes": leftover, "color": "0"}]

    kept_groups = {g["reuse"] for g in plan_groups if g.get("reuse")}
    out_nodes: list[dict] = []
    x0, y0 = 0, 0
    if plan.get("overview"):
        out_nodes.append({"id": "ai-overview", "type": "text", "text": plan["overview"], "x": x0, "y": y0,
                          "width": OVERVIEW_W, "height": OVERVIEW_H, "color": "6"})
        y0 += OVERVIEW_H + GROUP_GAP

    row_x, row_y, row_h, in_row = x0, y0, 0, 0
    placed_items: list[dict] = []
    for index, g in enumerate(plan_groups, 1):
        members = [by_id[nid] for nid in g.get("nodes", [])]
        col_w = max([size(m)[0] for m in members] + [DEFAULT_W])
        inner_w = max(col_w * COLUMNS + GAP * (COLUMNS - 1), DEFAULT_W)
        cursor_y = HEADER
        group_children: list[dict] = []
        if g.get("summary"):
            group_children.append({"id": f"ai-s{index}", "type": "text", "text": g["summary"], "x": PAD, "y": cursor_y,
                                   "width": inner_w, "height": SUMMARY_H, "color": g.get("color", "4")})
            cursor_y += SUMMARY_H + GAP
        for start in range(0, len(members), COLUMNS):
            row = members[start:start + COLUMNS]
            for col, m in enumerate(row):
                moved = dict(m)
                moved["x"], moved["y"] = PAD + col * (col_w + GAP), cursor_y
                group_children.append(moved)
            cursor_y += max(size(m)[1] for m in row) + GAP
        width = inner_w + PAD * 2
        height = max(cursor_y - GAP + PAD, HEADER + PAD)
        if in_row == GROUPS_PER_ROW:
            row_x, row_y, row_h, in_row = x0, row_y + row_h + GROUP_GAP, 0, 0
        gid = g["reuse"] if g.get("reuse") else f"ai-g{index}"
        group_node = dict(user_groups.get(gid, {}))
        group_node.update({"id": gid, "type": "group", "label": g.get("label", ""), "x": row_x, "y": row_y,
                           "width": width, "height": height})
        if g.get("color") and g["color"] != "0":
            group_node["color"] = g["color"]
        out_nodes.append(group_node)
        for child in group_children:
            child["x"] += row_x
            child["y"] += row_y
            placed_items.append(child)
        row_x += width + GROUP_GAP
        row_h = max(row_h, height)
        in_row += 1

    # 分组先写，内容后写：JSON Canvas 按数组顺序叠放，后面的在上层。
    data["nodes"] = out_nodes + placed_items
    dropped = [gid for gid in user_groups if gid not in kept_groups]
    ids = {n["id"] for n in data["nodes"]}
    data["edges"] = [e for e in data["edges"] if e.get("fromNode") in ids and e.get("toNode") in ids]
    save(path, data)
    print(f"已整理：{len(plan_groups)} 个分组，{len(placed_items)} 个节点。备份：{backup.name}")
    if dropped:
        print(f"去掉了没被沿用的用户分组：{'、'.join(user_groups[g].get('label', g) for g in dropped)}（备份里还在）")


def main() -> None:
    args = sys.argv[1:]
    if len(args) >= 2 and args[0] == "summary":
        workspace = Path(args[args.index("--workspace") + 1]) if "--workspace" in args else None
        summary(Path(args[1]), workspace)
    elif len(args) == 3 and args[0] == "apply":
        apply(Path(args[1]), Path(args[2]))
    else:
        print(__doc__)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
