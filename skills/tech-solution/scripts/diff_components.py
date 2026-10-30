#!/usr/bin/env python3
"""对比两版特征文件的选型结果，列出选型变化和骨架待办。技术方案升版时用。

用法：
    python3 diff_components.py <上一版特征.json> <这一版特征.json> [--json]

两份都是 select_components.py 认的特征文件。默认输出 Markdown；加 --json 输出结构化结果。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from select_components import FEATURE_IDS, select  # noqa: E402

FOLDERS = {
    "s01": "s01_agent_loop", "s02": "s02_tool_use", "s03": "s03_permission", "s04": "s04_hooks",
    "s05": "s05_todo_write", "s06": "s06_subagent", "s07": "s07_skill_loading", "s08": "s08_context_compact",
    "s09": "s09_memory", "s10": "s10_task_system", "s11": "s11_background_tasks", "s12": "s12_cron_scheduler",
    "s13": "s13_agent_teams", "s14": "s14_mcp_plugin", "s15": "s15_integrated_harness",
    "s16": "s16_workflow_runtime", "s17": "s17_goal_loop",
}
VALUE_WORD = {"yes": "需要", "later": "二期", "no": "不需要", "unknown": "待确认"}


def todo(comp_id: str, before: str, after: str) -> str:
    folder = FOLDERS[comp_id]
    if after == "必选":
        return f"按 参考组件/{folder}/README.md 补上 {comp_id}"
    if before == "必选" and after == "二期":
        return f"{comp_id} 推到二期：第一版不用做，已写的保留接口，先问产品经理要不要删"
    if before == "必选" and after == "放弃":
        return f"{comp_id} 不再需要：先问产品经理，确认后再删相关代码"
    if after == "二期":
        return f"{comp_id} 二期再做，第一版留好扩展位置"
    if after == "待确认":
        return f"{comp_id} 等待确认问题的回答，先不动代码"
    return "无"


def load(path: str) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"{path}：顶层必须是对象")
    unknown = sorted(set(data) - FEATURE_IDS)
    if unknown:
        raise SystemExit(f"{path}：不认识的特征 id {', '.join(unknown)}")
    return data


def diff(old: dict, new: dict) -> dict:
    before = {d["id"]: d for d in select(old)}
    after = {d["id"]: d for d in select(new)}
    components = [
        {"id": cid, "name": after[cid]["name"], "before": before[cid]["decision"], "after": after[cid]["decision"],
         "reason": after[cid]["reason"], "todo": todo(cid, before[cid]["decision"], after[cid]["decision"])}
        for cid in after if before[cid]["decision"] != after[cid]["decision"]
    ]
    features = [
        {"id": fid, "before": (old.get(fid) or {}).get("value", "unknown"), "after": (new.get(fid) or {}).get("value", "unknown"),
         "evidence": (new.get(fid) or {}).get("evidence", "")}
        for fid in sorted(FEATURE_IDS)
        if (old.get(fid) or {}).get("value", "unknown") != (new.get(fid) or {}).get("value", "unknown")
    ]
    return {"components": components, "features": features}


def markdown(result: dict) -> str:
    if not result["components"] and not result["features"]:
        return "选型没有变化。"
    lines = []
    if result["components"]:
        lines += ["| 组件 | 上一版 | 这一版 | 原因 | 骨架待办 |", "|---|---|---|---|---|"]
        lines += [f"| {c['id']} {c['name']} | {c['before']} | {c['after']} | {c['reason']} | {c['todo']} |" for c in result["components"]]
    else:
        lines.append("组件选型没有变化。")
    if result["features"]:
        lines += ["", "改了判断的特征：", ""]
        lines += [f"- `{f['id']}`：{VALUE_WORD[f['before']]} → {VALUE_WORD[f['after']]}（{f['evidence']}）" for f in result["features"]]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    result = diff(load(args[0]), load(args[1]))
    print(json.dumps(result, ensure_ascii=False, indent=2) if "--json" in argv else markdown(result))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
