#!/usr/bin/env python3
"""把技术方案第 2 节的特征判断表转成选型脚本要的特征文件。

用法：
    python3 features_from_md.py <技术方案.md> [-o <architecture-features.json>]

表格的第一列是带反引号的特征 id，另有「判断」「依据」两列；判断取 需要 / 二期 / 不需要 / 待确认
（也认 yes / later / no / unknown）。表里缺的特征按 unknown 处理，并在标准错误里列出来。
不给 -o 时把 JSON 打到标准输出。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from select_components import FEATURES  # noqa: E402

VALUE_BY_WORD = {"需要": "yes", "二期": "later", "不需要": "no", "待确认": "unknown",
                 "yes": "yes", "later": "later", "no": "no", "unknown": "unknown"}
FEATURE_ORDER = [feature_id for feature_id, _, _ in FEATURES]


def cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse(prd: str) -> tuple[dict, list[str]]:
    """返回 (特征文件内容, 问题列表)。没找到表时特征文件为空。"""
    features: dict[str, dict] = {}
    problems: list[str] = []
    judge_col = evidence_col = None
    for line in prd.splitlines():
        if not line.lstrip().startswith("|"):
            judge_col = evidence_col = None
            continue
        row = cells(line)
        if "判断" in row and "依据" in row:
            judge_col, evidence_col = row.index("判断"), row.index("依据")
            continue
        if judge_col is None or not row:
            continue
        match = re.fullmatch(r"`([a-z_]+)`", row[0])
        if not match or match.group(1) not in FEATURE_ORDER:
            continue
        feature_id = match.group(1)
        word = row[judge_col] if judge_col < len(row) else ""
        evidence = row[evidence_col] if evidence_col < len(row) else ""
        value = VALUE_BY_WORD.get(word.strip().lower() if word.isascii() else word.strip())
        if value is None:
            problems.append(f"{feature_id} 的判断「{word or '空'}」不认识，按待确认处理")
            value = "unknown"
        features[feature_id] = {"value": value, "evidence": evidence or "PRD 特征表没写依据"}
    missing = [f for f in FEATURE_ORDER if f not in features]
    if features and missing:
        problems.append("表里缺这些特征，按待确认处理：" + "、".join(missing))
        for feature_id in missing:
            features[feature_id] = {"value": "unknown", "evidence": "PRD 特征表里没有这一行"}
    ordered = {f: features[f] for f in FEATURE_ORDER if f in features}
    return ordered, problems


def main(argv: list[str]) -> int:
    out = None
    if "-o" in argv:
        i = argv.index("-o")
        if i + 1 >= len(argv):
            print(__doc__, file=sys.stderr)
            return 2
        out = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    if len(argv) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    features, problems = parse(Path(argv[0]).read_text(encoding="utf-8"))
    if not features:
        print("PRD 里没有找到「Agent 特征判断」表（列名要有「判断」和「依据」，第一列是带反引号的特征 id）。", file=sys.stderr)
        return 1
    for problem in problems:
        print("提示：" + problem, file=sys.stderr)
    text = json.dumps(features, ensure_ascii=False, indent=2)
    if out:
        Path(out).write_text(text + "\n", encoding="utf-8")
        counts = {v: sum(1 for f in features.values() if f["value"] == v) for v in ("yes", "later", "no", "unknown")}
        print(f"已写入 {out}：需要 {counts['yes']}、二期 {counts['later']}、不需要 {counts['no']}、待确认 {counts['unknown']}", file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
