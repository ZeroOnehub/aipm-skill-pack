#!/usr/bin/env python3
"""Agent 组件选型：特征判断 → 组件决定。纯规则，同样的输入永远得到同样的选型。

用法：
    python3 select_components.py <特征.json> [--json]

特征.json 的格式：
    {"destructive_ops": {"value": "yes", "evidence": "一句话依据"}, ...}
value 只能是 yes / no / later / unknown；缺的特征按 unknown 处理。
默认输出 Markdown 表格；加 --json 输出结构化结果。
"""

from __future__ import annotations

import json
import sys

DECISION_BY_VALUE = {"yes": "必选", "later": "二期", "unknown": "待确认", "no": "放弃"}

# (特征 id, 判断问题, 触发的组件 id)
FEATURES = [
    ("destructive_ops", "是否涉及破坏性或敏感操作（删除、写入外部系统、支付、发送消息、隐私数据）？", "s03"),
    ("audit_needed", "是否需要审计、拦截、埋点、合规记录？", "s04"),
    ("multi_step", "单次交付是否需要先列计划再逐步推进并跟踪进度（多轮、可中断、要汇报进展）？固定顺序调用几个工具不算。", "s05"),
    ("context_heavy", "是否会出现上下文爆炸的子任务，或可并行的探索型子任务？", "s06"),
    ("large_knowledge", "领域知识库是否庞大、需要按需加载？", "s07"),
    ("long_sessions", "会话是否很长、工具输出或日志量是否很大？", "s08"),
    ("cross_session_memory", "是否需要跨会话记住用户偏好、决策、历史？", "s09"),
    ("persistent_goals", "目标是否需要持久化、支持断点续跑？", "s10"),
    ("slow_operations", "是否有耗时几分钟以上的慢操作需要不阻塞主流程？", "s11"),
    ("scheduled", "是否需要定时自动触发？", "s12"),
    ("parallel_isolated", "是否需要多任务并行且各自隔离工作区（多 Agent 团队）？", "s13"),
    ("external_ecosystem", "是否需要接入外部工具生态（MCP、第三方插件）？", "s14"),
    ("fixed_orchestration", "输入是否把流程写成固定的阶段序列且各阶段无需模型临场决策？只描述产品体验、或流程里有模型判断分支的不算。", "s16"),
    ("auto_completion", "是否需要自动判断「何时算完成」（独立评估器）？", "s17"),
]

# (组件 id, 名称, 什么时候需要, 生产级要点, 是否恒选)
COMPONENTS = [
    ("s01", "Agent Loop", "一切基础：循环 + 工具", "重试、超时、token 上限、stop_reason 完整处理", True),
    ("s02", "工具系统", "需要调用外部系统/API/数据源", "JSON schema 严格、参数校验、错误回传格式统一", True),
    ("s03", "权限系统", "涉及破坏性/敏感操作", "白名单/黑名单、破坏性操作二次确认、审计日志、默认拒绝", False),
    ("s04", "钩子系统", "需要审计、拦截、埋点", "调用前可阻断、调用后可观察、异常不影响主循环", False),
    ("s05", "任务规划", "多步骤、需跟踪进度", "计划持久化、状态流转、进度可查询", False),
    ("s06", "子 Agent", "上下文会爆、任务可并行", "独立消息列表、最终文本回传、超时回收", False),
    ("s07", "技能加载", "领域知识库庞大", "目录先行、按需展开、版本管理", False),
    ("s08", "上下文压缩", "长会话、日志量大", "分层压缩、先裁工具结果再摘要历史、保留权威指令", False),
    ("s09", "记忆系统", "需跨会话记住偏好/决策", "筛选→提取→整合、持久化 + 检索、冲突时用户指令优先", False),
    ("s10", "任务系统", "目标需持久化、断点续跑", "文件持久化、依赖图、原子状态变更、并发锁", False),
    ("s11", "后台任务", "有慢操作需不阻塞", "线程池、完成通知注入、超时与清理", False),
    ("s12", "定时调度", "需定时自治触发", "持久化调度、幂等、会话级作用域", False),
    ("s13", "Agent 团队", "多任务并行、需隔离工作区", "原子认领、任务绑定独立工作区、异步邮箱、关停流程", False),
    ("s14", "MCP 插件", "需接入外部工具生态", "工具发现、命名空间、连接失败降级", False),
    ("s15", "集成 Harness", "上述机制需协同（选了 3 个以上可选组件）", "单一循环、动态重建系统提示词、共享客户端", False),
    ("s16", "工作流运行时", "编排形态固定", "脚本拥有编排、生命周期事件、断点续跑日志", False),
    ("s17", "目标闭环", "需自动判断「何时算完成」", "独立评估器、目标不可能/失败/超限时交还控制权", False),
]

FEATURE_IDS = {feature_id for feature_id, _, _ in FEATURES}


def select(features: dict) -> list[dict]:
    """按规则给出 17 个组件的决定，顺序与 COMPONENTS 一致。"""
    by_component: dict[str, dict] = {}
    for comp_id, name, when, points, always in COMPONENTS:
        if always:
            by_component[comp_id] = {"id": comp_id, "name": name, "decision": "必选", "reason": when + "（恒选）", "points": points}

    for feature_id, question, comp_id in FEATURES:
        _, name, when, points, _ = next(c for c in COMPONENTS if c[0] == comp_id)
        raw = features.get(feature_id) or {}
        value = raw.get("value", "unknown")
        if value not in DECISION_BY_VALUE:
            value = "unknown"
        evidence = str(raw.get("evidence") or "").strip()
        decision = DECISION_BY_VALUE[value]
        if decision == "待确认":
            reason = f"输入未说明：{question}"
        elif decision == "放弃":
            reason = evidence or f"输入表明不需要：{when}"
        else:
            reason = evidence or when
        by_component[comp_id] = {"id": comp_id, "name": name, "decision": decision, "reason": reason, "points": points, "feature": feature_id}

    optional = [d for d in by_component.values() if d["id"] not in ("s01", "s02")]
    mvp = [d["id"] for d in optional if d["decision"] == "必选"]
    later = [d["id"] for d in optional if d["decision"] in ("必选", "二期")]
    _, name15, _, points15, _ = next(c for c in COMPONENTS if c[0] == "s15")
    if len(mvp) >= 3:
        d15 = ("必选", f"第一版已选 {len(mvp)} 个可选组件（{', '.join(mvp)}），需归一到单一循环")
    elif len(later) >= 3:
        d15 = ("二期", f"含二期共 {len(later)} 个可选组件，二期集成时需要")
    else:
        d15 = ("放弃", "可选组件不足 3 个，直接在主循环里挂接即可")
    by_component["s15"] = {"id": "s15", "name": name15, "decision": d15[0], "reason": d15[1], "points": points15}

    return [by_component[comp_id] for comp_id, *_ in COMPONENTS]


def markdown(decisions: list[dict]) -> str:
    mark = {"必选": "✅ 必选", "二期": "⏸ 二期", "待确认": "❓ 待确认", "放弃": "❌ 放弃"}
    lines = ["| 组件 | 选否 | 理由 | 生产级要点 |", "|---|---|---|---|"]
    for d in decisions:
        points = d["points"] if d["decision"] in ("必选", "二期") else ""
        lines.append(f"| {d['id']} {d['name']} | {mark[d['decision']]} | {d['reason']} | {points} |")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    with open(args[0], encoding="utf-8") as handle:
        features = json.load(handle)
    if not isinstance(features, dict):
        print("特征文件的顶层必须是对象：{特征 id: {value, evidence}}", file=sys.stderr)
        return 2
    unknown_keys = sorted(set(features) - FEATURE_IDS)
    if unknown_keys:
        print(f"不认识的特征 id：{', '.join(unknown_keys)}。可用的有：{', '.join(sorted(FEATURE_IDS))}", file=sys.stderr)
        return 2
    decisions = select(features)
    if "--json" in argv:
        print(json.dumps(decisions, ensure_ascii=False, indent=2))
    else:
        print(markdown(decisions))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
