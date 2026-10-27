#!/usr/bin/env python3
"""静态扫描一个项目：目录、依赖、模型调用、17 个组件的代码信号、六条落地标准的线索。只读，不运行项目。

用法：
    python3 scan_project.py <项目目录> [--expect <architecture-features.json>] [--json]

- 默认输出 Markdown。--json 输出结构化结果（含全部命中行）。
- --expect：按特征文件算出「应有」的组件，和扫描结果对照，给出差距表和优先级。
- 自动跳过依赖、构建产物、隐藏目录，以及「参考组件」「手册」两个文件夹（那是参考资料，不是产品代码）。
- 信号只是关键词命中：「没扫到」不等于「没实现」，「扫到」也不等于「做对了」，要打开命中的位置确认。
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

EXCLUDE_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", "dist", "build", "out",
                ".next", ".idea", ".vscode", "archive", ".mypy_cache", ".ruff_cache", "target", "vendor",
                "参考组件", "手册", "evidence"}
CODE_EXT = {".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".rb", ".kt", ".swift", ".sh"}
TEXT_EXT = CODE_EXT | {".md", ".yaml", ".yml", ".toml", ".json", ".txt", ".cfg", ".ini"}
MAX_FILE_BYTES = 400_000
MAX_HITS = 12

# (组件 id, 名称, 代码信号正则)
COMPONENTS = [
    ("s01", "Agent Loop", (r"tool_use", r"tool_calls", r"messages\.create", r"chat\.completions", r"function_call", r"agent_loop", r"while\s+True")),
    ("s02", "工具系统", (r"input_schema", r"TOOL_HANDLERS", r"\"parameters\"\s*:", r"def run_\w+\(", r"@tool", r"tools\s*=\s*\[")),
    ("s03", "权限系统", (r"permission", r"DENY_LIST", r"allow.?list", r"\bdeny\b", r"check_permission", r"is_relative_to", r"safe_path")),
    ("s04", "钩子系统", (r"PreToolUse", r"PostToolUse", r"register_hook", r"trigger_hooks", r"\bhooks?\b", r"middleware", r"interceptor")),
    ("s05", "任务规划", (r"todo_write", r"TodoManager", r"\btodos?\b", r"plan(?:ning)?_step", r"checklist")),
    ("s06", "子 Agent", (r"subagent", r"sub_agent", r"spawn_subagent", r"run_subagent", r"delegate", r"child_agent")),
    ("s07", "技能加载", (r"SKILL\.md", r"load_skill", r"SkillLoader", r"skills_dir", r"knowledge_base", r"\brag\b", r"retriev")),
    ("s08", "上下文压缩", (r"compact", r"summariz", r"truncat", r"context_window", r"micro_compact", r"prompt_too_long")),
    ("s09", "记忆系统", (r"MEMORY\.md", r"\.memory", r"memor(?:y|ies)", r"remember", r"consolidate")),
    ("s10", "任务系统", (r"TaskStore", r"blockedBy", r"\.tasks/", r"claim_task", r"complete_task", r"task_graph")),
    ("s11", "后台任务", (r"run_in_background", r"BackgroundManager", r"threading\.Thread", r"task_notification", r"asyncio\.create_task", r"celery", r"\bqueue\b")),
    ("s12", "定时调度", (r"\bcron\b", r"schedule", r"scheduled_tasks", r"apscheduler", r"every\s+\d+", r"\binterval\b")),
    ("s13", "Agent 团队", (r"teammate", r"worktree", r"MessageBus", r"\.mailboxes", r"spawn_teammate", r"\bcrew\b", r"swarm")),
    ("s14", "MCP 插件", (r"\bmcp\b", r"mcp__", r"MCPClient", r"connect_mcp", r"tools/list", r"tools/call", r"plugin")),
    ("s15", "集成 Harness", (r"assemble_system_prompt", r"assemble_tool_pool", r"integrated", r"harness")),
    ("s16", "工作流运行时", (r"workflow", r"journal", r"pipeline\(", r"WorkflowRunner", r"langgraph", r"state_machine", r"\bdag\b")),
    ("s17", "目标闭环", (r"\bgoal\b", r"evaluator", r"\bjudge\b", r"acceptance", r"verify_done", r"is_complete", r"stop_hook")),
]
FOLDERS = {
    "s01": "s01_agent_loop", "s02": "s02_tool_use", "s03": "s03_permission", "s04": "s04_hooks", "s05": "s05_todo_write",
    "s06": "s06_subagent", "s07": "s07_skill_loading", "s08": "s08_context_compact", "s09": "s09_memory",
    "s10": "s10_task_system", "s11": "s11_background_tasks", "s12": "s12_cron_scheduler", "s13": "s13_agent_teams",
    "s14": "s14_mcp_plugin", "s15": "s15_integrated_harness", "s16": "s16_workflow_runtime", "s17": "s17_goal_loop",
}
LLM_SDKS = {
    "anthropic": r"\bimport anthropic\b|\bfrom anthropic\b|@anthropic-ai/sdk|Anthropic\(",
    "openai": r"\bimport openai\b|\bfrom openai\b|from \"openai\"|OpenAI\(",
    "兼容接口（直接 HTTP）": r"/chat/completions|/v1/messages",
    "langchain": r"\blangchain\b",
    "litellm": r"\blitellm\b",
}
ACCEPTANCE = {
    "可运行": [r"if __name__ == .__main__.", r"def main\(", r"\"scripts\"\s*:", r"argparse", r"FastAPI\(", r"uvicorn"],
    "可容错": [r"\bretry\b", r"\btimeout\b", r"backoff", r"fallback", r"except \w+Error", r"catch \("],
    "可观测": [r"\blogging\b", r"logger\.", r"\bmetrics?\b", r"trajector", r"\.jsonl", r"opentelemetry"],
    "可测试": [r"(^|/)tests?/", r"test_\w+\.py$", r"\.test\.(ts|js|tsx)$", r"_test\.go$"],
    "可部署": [r"(^|/)Dockerfile$", r"docker-compose", r"(^|/)Procfile$", r"(^|/)Makefile$", r"deploy", r"vercel\.json"],
    "可度量": [r"成功率", r"准确率", r"完成率", r"\blatency\b", r"\bcost\b", r"success_rate", r"track\(", r"analytics"],
}
FILENAME_KEYS = ("可测试", "可部署")


def iter_files(root: Path):
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")
                         and not (Path(directory) / d).is_symlink())
        for name in sorted(files):
            path = Path(directory) / name
            if (name.startswith(".") and name != ".env.example") or path.is_symlink() or not path.is_file():
                continue
            yield path


def tree(root: Path, depth: int = 3, limit: int = 80) -> list[str]:
    lines: list[str] = []

    def walk(d: Path, level: int) -> None:
        if level > depth or len(lines) >= limit:
            return
        try:
            entries = sorted(d.iterdir(), key=lambda p: (not p.is_dir(), p.name))
        except OSError:
            return
        for e in entries:
            if e.is_symlink() or e.name in EXCLUDE_DIRS or (e.name.startswith(".") and e.name != ".env.example"):
                continue
            if len(lines) >= limit:
                lines.append("  " * level + "…")
                return
            lines.append("  " * level + e.name + ("/" if e.is_dir() else ""))
            if e.is_dir():
                walk(e, level + 1)

    walk(root, 0)
    return lines


def is_test(rel: Path) -> bool:
    return any(p in {"test", "tests", "__tests__", "evals"} for p in rel.parts) or bool(
        re.search(r"(^test_|_test\.py$|\.test\.|\.spec\.|_test\.go$)", rel.name))


def scan(root: Path) -> dict:
    compiled = {cid: [re.compile(p, re.I) for p in pats] for cid, _, pats in COMPONENTS}
    sdk = {k: re.compile(v) for k, v in LLM_SDKS.items()}
    acc = {k: [re.compile(p, re.I | re.M) for p in v] for k, v in ACCEPTANCE.items()}
    result = {"root": str(root), "files": 0, "tests": [], "entry_points": [], "llm": {}, "config": [],
              "components": {cid: {"name": name, "hits": [], "code_files": set(), "hit_count": 0} for cid, name, _ in COMPONENTS},
              "acceptance": {k: [] for k in ACCEPTANCE}}
    for path in iter_files(root):
        rel = path.relative_to(root)
        srel = rel.as_posix()
        result["files"] += 1
        if path.name in (".env.example", "pyproject.toml", "package.json", "requirements.txt", "config.yaml"):
            result["config"].append(srel)
        for key in FILENAME_KEYS:
            if len(result["acceptance"][key]) < 6 and any(p.search(srel) for p in acc[key]):
                result["acceptance"][key].append(srel)
        if path.suffix not in TEXT_EXT:
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        code = path.suffix in CODE_EXT and not is_test(rel)
        if path.suffix in CODE_EXT and is_test(rel):
            result["tests"].append(srel)
        if not code:
            continue
        lines = text.splitlines()
        if re.search(r"if __name__ == .__main__.|def main\(|FastAPI\(", text):
            result["entry_points"].append(srel)
        for name, pat in sdk.items():
            for i, line in enumerate(lines, 1):
                if pat.search(line):
                    result["llm"].setdefault(name, []).append(f"{srel}:{i}")
                    break
        for cid, pats in compiled.items():
            comp = result["components"][cid]
            for i, line in enumerate(lines, 1):
                if any(p.search(line) for p in pats):
                    comp["hit_count"] += 1
                    comp["code_files"].add(srel)
                    if len(comp["hits"]) < MAX_HITS:
                        comp["hits"].append(f"{srel}:{i}  {line.strip()[:100]}")
        for key, pats in acc.items():
            if key in FILENAME_KEYS or len(result["acceptance"][key]) >= 6:
                continue
            for p in pats:
                m = p.search(text)
                if m:
                    result["acceptance"][key].append(f"{srel}:{text.count(chr(10), 0, m.start()) + 1}")
                    break
    for comp in result["components"].values():
        files = len(comp["code_files"])
        comp["strength"] = "强" if files >= 2 or comp["hit_count"] >= 4 else ("弱" if files else "无")
        comp["code_files"] = sorted(comp["code_files"])
    if result["tests"]:
        result["acceptance"]["可测试"] = sorted(set(result["acceptance"]["可测试"]) | set(result["tests"][:3]))[:6]
    result["tree"] = tree(root)
    return result


def expected(features_path: Path) -> dict[str, str]:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "agent-architecture" / "scripts"))
    from select_components import select  # noqa: PLC0415
    features = json.loads(features_path.read_text(encoding="utf-8"))
    return {d["id"]: d["decision"] for d in select(features)}


def gaps(result: dict, expect: dict[str, str]) -> list[dict]:
    rows = []
    for cid, comp in result["components"].items():
        want, have = expect.get(cid, "待确认"), comp["strength"]
        if want == "必选":
            verdict, priority = {"无": ("缺失", "P0"), "弱": ("只有雏形", "P1"), "强": ("有信号，打开确认", "—")}[have]
        elif want == "二期":
            verdict, priority = ("二期再做", "P2") if have == "无" else ("已有雏形（二期项）", "—")
        elif want == "放弃":
            verdict, priority = ("不需要", "—") if have == "无" else ("方案没选但代码里有，确认是否多做了", "P2")
        else:
            verdict, priority = ("待确认", "?")
        rows.append({"id": cid, "name": comp["name"], "expect": want, "have": have, "verdict": verdict,
                     "priority": priority, "where": comp["hits"][:2], "reference": f"参考组件/{FOLDERS[cid]}/README.md"})
    order = {"P0": 0, "P1": 1, "P2": 2, "?": 3, "—": 4}
    return sorted(rows, key=lambda r: (order[r["priority"]], r["id"]))


def markdown(result: dict, rows: list[dict] | None) -> str:
    out = [f"# 静态扫描：{result['root']}", "",
           f"- 文件 {result['files']} 个，测试文件 {len(result['tests'])} 个，入口 {', '.join(result['entry_points'][:5]) or '没找到'}",
           f"- 模型调用：{'；'.join(f'{k}（{v[0]}）' for k, v in result['llm'].items()) or '没找到'}",
           f"- 配置与依赖：{', '.join(result['config']) or '没找到'}", "",
           "> 信号是关键词命中：没扫到不等于没实现，扫到也不等于做对了，结论前打开命中位置确认。", ""]
    if rows is not None:
        out += ["## 组件差距（按架构方案的选型对照）", "", "| 优先级 | 组件 | 应有 | 扫描 | 判定 | 命中位置 | 去哪看 |", "|---|---|---|---|---|---|---|"]
        out += [f"| {r['priority']} | {r['id']} {r['name']} | {r['expect']} | {r['have']} | {r['verdict']} | "
                f"{'<br>'.join(w.split('  ')[0] for w in r['where']) or '—'} | {r['reference']} |" for r in rows]
    else:
        out += ["## 组件信号", "", "| 组件 | 强度 | 命中文件数 | 命中位置（前两处） |", "|---|---|---|---|"]
        out += [f"| {cid} {c['name']} | {c['strength']} | {len(c['code_files'])} | {'<br>'.join(h.split('  ')[0] for h in c['hits'][:2]) or '—'} |"
                for cid, c in result["components"].items()]
    out += ["", "## 六条落地标准的线索", "", "| 标准 | 线索 |", "|---|---|"]
    out += [f"| {k} | {', '.join(v) or '没找到'} |" for k, v in result["acceptance"].items()]
    out += ["", "## 目录（前三层）", "", "```", *result["tree"], "```"]
    return "\n".join(out)


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    expect_path = None
    if "--expect" in argv:
        i = argv.index("--expect")
        if i + 1 >= len(argv):
            print(__doc__, file=sys.stderr)
            return 2
        expect_path = Path(argv[i + 1])
        args = [a for a in args if a != argv[i + 1]]
    if len(args) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    root = Path(args[0]).expanduser().resolve()
    if not root.is_dir():
        print(f"不是目录：{root}", file=sys.stderr)
        return 2
    result = scan(root)
    rows = gaps(result, expected(expect_path)) if expect_path else None
    if "--json" in argv:
        print(json.dumps({**result, "gaps": rows}, ensure_ascii=False, indent=2))
    else:
        print(markdown(result, rows))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
