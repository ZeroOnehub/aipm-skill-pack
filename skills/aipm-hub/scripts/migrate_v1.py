#!/usr/bin/env python3
"""把老格式（version 1，老六阶段）的拾阶项目升级到新流程（version 2，六个节点）。只在用户同意后运行。

用法：
    python3 migrate_v1.py <项目根目录> [--dry-run]

做的事：
- 01-立项、02-PRD、03-原型交互 原样保留，状态和站照旧。
- 04-AI方案设计 的内容搬进 04-技术方案/旧版-AI方案设计/；05-评测 → 05-模型评测/旧版-评测/；
  06-上线复盘 → 06-MVP/旧版-上线复盘/。旧目录搬空后删除。文件一个不删。
- aipm.json：version 改为 2；技术方案、模型评测、MVP 三个节点记 not_started，note 写旧版材料在哪；
  上线复盘节点去掉（材料已搬走）；currentStage 和 pending 里的阶段 id 按映射改；
  老的开发文件夹（build）保留并标 legacy，项目面板会按老的研发阶段名显示。
- 升级前把 aipm.json 备份为 aipm.v1.json。
--dry-run 只打印要做什么，不改任何文件。
"""

from __future__ import annotations

import datetime as dt
import json
import shutil
import sys
from pathlib import Path

MOVES = [
    ("04-AI方案设计", "04-技术方案", "旧版-AI方案设计"),
    ("05-评测", "05-模型评测", "旧版-评测"),
    ("06-上线复盘", "06-MVP", "旧版-上线复盘"),
]
STAGE_MAP = {"ai-design": "tech", "evaluation": "model-eval", "launch-review": "mvp"}
NEW_ORDER = ["initiation", "prd", "prototype", "tech", "model-eval", "mvp"]
NOTES = {
    "tech": "旧版 AI 方案设计的产出在 04-技术方案/旧版-AI方案设计/，可以作为技术方案的输入",
    "model-eval": "旧版评测的产出在 05-模型评测/旧版-评测/，样例可以并进新评测集",
    "mvp": "旧版上线复盘的材料在 06-MVP/旧版-上线复盘/",
}


def has_files(path: Path) -> bool:
    return path.is_dir() and any(p.is_file() and p.name != ".DS_Store" for p in path.rglob("*"))


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--dry-run"]
    dry = "--dry-run" in sys.argv
    if len(args) != 1:
        print(__doc__)
        raise SystemExit(1)
    root = Path(args[0]).expanduser().resolve()
    meta = root / "aipm.json"
    data = json.loads(meta.read_text(encoding="utf-8"))
    if data.get("version") == 2:
        raise SystemExit("已经是新格式（version 2），不用升级。")

    plan: list[str] = []
    moved_old: dict[str, bool] = {}
    for old, new, sub in MOVES:
        src, dst = root / old, root / new / sub
        moved_old[new] = has_files(src)
        if moved_old[new]:
            plan.append(f"搬：{old}/ → {new}/{sub}/")
        elif src.exists():
            plan.append(f"删空目录：{old}/")
        plan.append(f"建：{new}/")

    old_stages = {s.get("id"): s for s in data.get("stages", []) if isinstance(s, dict)}
    stages = []
    for sid in NEW_ORDER:
        if sid in ("initiation", "prd", "prototype") and sid in old_stages:
            stages.append(old_stages[sid])
            continue
        entry = {"id": sid, "status": "not_started"}
        folder = {"tech": "04-技术方案", "model-eval": "05-模型评测", "mvp": "06-MVP"}[sid]
        if moved_old.get(folder):
            entry["note"] = NOTES[sid]
        stages.append(entry)
    data["stages"] = stages
    data["version"] = 2
    data["currentStage"] = STAGE_MAP.get(data.get("currentStage"), data.get("currentStage") or "initiation")
    for item in data.get("pending", []):
        if isinstance(item, dict) and item.get("stage") in STAGE_MAP:
            item["stage"] = STAGE_MAP[item["stage"]]
        if isinstance(item, dict) and isinstance(item.get("source"), str):
            for old, new, sub in MOVES:
                if item["source"].startswith(old + "/"):
                    item["source"] = f"{new}/{sub}/" + item["source"][len(old) + 1:]
    if isinstance(data.get("build"), dict):
        data["build"]["legacy"] = True
        plan.append("保留老的开发文件夹（build），标 legacy")
    data["updated"] = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    plan.append("aipm.json → version 2（原文件备份为 aipm.v1.json）")

    print(f"项目：{root.name}")
    for line in plan:
        print(f"- {line}")
    if dry:
        print("\n（--dry-run：没有改动任何文件）")
        return

    shutil.copy2(meta, root / "aipm.v1.json")
    for old, new, sub in MOVES:
        src, dst = root / old, root / new / sub
        (root / new).mkdir(exist_ok=True)
        if has_files(src):
            dst.mkdir(parents=True, exist_ok=True)
            for child in list(src.iterdir()):
                if child.name == ".DS_Store":
                    child.unlink()
                    continue
                shutil.move(str(child), str(dst / child.name))
        if src.exists():
            leftovers = [p for p in src.rglob("*") if p.is_file() and p.name != ".DS_Store"]
            if not leftovers:
                shutil.rmtree(src)
    meta.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("\n已升级。")


if __name__ == "__main__":
    main()
