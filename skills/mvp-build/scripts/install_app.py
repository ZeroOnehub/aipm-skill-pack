#!/usr/bin/env python3
"""把拾阶项目装成一个 MVP 代码仓库（默认 <项目>/06-MVP/app/），或者在 PRD、技术方案升版后同步过去。

用法：
    python3 install_app.py --project <项目根目录> [--app <MVP 目录>] [--tool 拾阶|Claude Code|Codex|研发团队] [--sync]

第一次运行：
- 复制规则卡、手册、verify.sh、模板；已存在且改过的文件不覆盖。git init。
- docs/拾阶/ 放入 PRD、技术方案、决策台账、评测（方案、报告、评测集、run_eval.py）、原型、scan_project.py。
- 从 PRD「Agent 提示词设计」一节抽出每个 Agent 的提示词，写成 prompts/<名字>.md（已有的不覆盖）。
- 按 04-技术方案/architecture-features.json 的选型，把「必选」组件复制进 参考组件/。
- 建 docs/项目状态.md（阶段 0 开发准备，决策台账抄自技术方案）。
- 在 aipm.json 写入 build（产品面板的研发进度卡读它）。
--sync：只刷新 docs/拾阶/；有变化的文件旧版存进 docs/拾阶/历史/，并在 docs/拾阶/同步记录.md 记一条。不碰代码和项目状态。
"""

from __future__ import annotations

import argparse
import datetime as dt
import filecmp
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
SKILLS = SKILL.parent
APP_TEMPLATE = SKILL / "templates" / "app"
COMPONENTS = SKILLS / "tech-solution" / "references" / "components"
SELECTOR = SKILLS / "tech-solution" / "scripts"
RUN_EVAL = SKILLS / "model-eval" / "scripts" / "run_eval.py"
SKIP = {".DS_Store", "__pycache__"}
COMPONENT_SHARED = ("README.md", "requirements.txt", ".env.example", "common")

report: dict[str, list[str]] = {"新建": [], "更新": [], "保留已有": [], "提示": []}


def note(kind: str, text: str) -> None:
    report[kind].append(text)


def files_under(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_file() and not SKIP.intersection(path.parts):
            yield path


def place(src: Path, dst: Path, label: str, *, overwrite: bool) -> bool:
    """复制一个文件。返回是否有变化。"""
    if dst.exists():
        if filecmp.cmp(src, dst, shallow=False):
            return False
        if not overwrite:
            note("保留已有", label)
            return False
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        note("更新", label)
        return True
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    note("新建", label)
    return True


def handoff_sources(project: Path) -> list[tuple[Path, str]]:
    """拾阶这边要交过去的文件：(源文件, docs/拾阶/ 下的相对路径)。"""
    pairs: list[tuple[Path, str]] = []
    fixed = [
        ("02-PRD/PRD.md", "PRD.md"),
        ("04-技术方案/技术方案.md", "技术方案.md"),
        ("04-技术方案/决策台账.md", "决策台账.md"),
        ("04-技术方案/技术适配声明.md", "技术适配声明.md"),
        ("04-技术方案/architecture-features.json", "architecture-features.json"),
        ("05-模型评测/评测方案.md", "评测/评测方案.md"),
        ("05-模型评测/评测报告.md", "评测/评测报告.md"),
        ("05-模型评测/候选模型表.md", "评测/候选模型表.md"),
        ("03-原型交互/页面清单.md", "原型/页面清单.md"),
    ]
    for src, rel in fixed:
        if (project / src).is_file():
            pairs.append((project / src, rel))
    for html in sorted((project / "03-原型交互").glob("*.html")):
        pairs.append((html, f"原型/{html.name}"))
    eval_set = project / "05-模型评测" / "评测集"
    if eval_set.is_dir():
        for f in files_under(eval_set):
            pairs.append((f, f"评测/评测集/{f.relative_to(eval_set)}"))
    pairs.append((RUN_EVAL, "评测/run_eval.py"))
    pairs.append((HERE / "scan_project.py", "scan_project.py"))
    pairs.append((SELECTOR / "select_components.py", "select_components.py"))
    return pairs


def sync_handoff(project: Path, app: Path, first: bool) -> list[str]:
    base = app / "docs" / "拾阶"
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    changed: list[str] = []
    for src, rel in handoff_sources(project):
        dst = base / rel
        if dst.exists() and not filecmp.cmp(src, dst, shallow=False) and not first and src.suffix == ".md":
            history = base / "历史" / f"{Path(rel).stem}-{stamp}{Path(rel).suffix}"
            history.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dst, history)
        if place(src, dst, f"docs/拾阶/{rel}", overwrite=True):
            changed.append(rel)
    return changed


def extract_prompts(prd: Path, app: Path) -> None:
    """PRD「Agent 提示词设计」一节：每个四级标题下第一个代码块就是这个 Agent 的提示词。"""
    if not prd.is_file():
        return
    text = prd.read_text(encoding="utf-8")
    start = text.find("Agent 提示词设计")
    if start < 0:
        note("提示", "PRD 里没有「Agent 提示词设计」一节，prompts/ 留空，开发时照 PRD 手动放")
        return
    section = text[start:]
    end = re.search(r"\n### (?!#)", section[10:])
    if end:
        section = section[: end.start() + 10]
    found = 0
    for match in re.finditer(r"^#### (.+?)\n(.*?)(?=^#### |\Z)", section, re.M | re.S):
        name = re.sub(r"[\\/:*?\"<>|\s]+", "", match.group(1).replace("Agent", "")) or f"环节{found + 1}"
        block = re.search(r"```[a-zA-Z]*\n(.*?)```", match.group(2), re.S)
        if not block:
            continue
        dst = app / "prompts" / f"{name}.md"
        found += 1
        if dst.exists():
            note("保留已有", f"prompts/{name}.md")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(f"<!-- 第一版取自 PRD「Agent 提示词设计」{match.group(1).strip()}。改提示词请回拾阶 PRD 升版。 -->\n"
                       + block.group(1), encoding="utf-8")
        note("新建", f"prompts/{name}.md")
    if found == 0:
        note("提示", "PRD「Agent 提示词设计」下没找到 #### 标题加代码块的提示词，prompts/ 留空")


def install_components(project: Path, app: Path) -> None:
    features_file = project / "04-技术方案" / "architecture-features.json"
    if not features_file.exists():
        note("提示", "没有 04-技术方案/architecture-features.json（形态不是 Agent，或还没选型），不复制参考组件")
        return
    sys.path.insert(0, str(SELECTOR))
    from select_components import select  # noqa: PLC0415
    ids = [d["id"] for d in select(json.loads(features_file.read_text(encoding="utf-8"))) if d["decision"] == "必选"]
    folders = {p.name[:3]: p for p in COMPONENTS.iterdir() if p.is_dir() and re.match(r"s\d\d_", p.name)}
    dest = app / "参考组件"
    for name in COMPONENT_SHARED:
        src = COMPONENTS / name
        for f in (files_under(src) if src.is_dir() else [src]):
            place(f, dest / f.relative_to(COMPONENTS), f"参考组件/{f.relative_to(COMPONENTS)}", overwrite=True)
    for cid in ids:
        for f in files_under(folders[cid]):
            place(f, dest / f.relative_to(COMPONENTS), f"参考组件/{f.relative_to(COMPONENTS)}", overwrite=True)
    note("提示", f"参考组件：{'、'.join(ids)}")


def status_file(project: Path, app: Path, name: str) -> None:
    dst = app / "docs" / "项目状态.md"
    if dst.exists():
        return
    ledger = project / "04-技术方案" / "决策台账.md"
    table = "（技术方案还没有决策台账，开工时补）"
    if ledger.is_file():
        rows = [line for line in ledger.read_text(encoding="utf-8").splitlines() if line.startswith("|")]
        if rows:
            table = "\n".join(rows)
    today = dt.date.today().isoformat()
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(f"""# 项目状态：{name}

## 当前阶段
- 阶段：0 开发准备
- 最近更新：{today}
- 上次停在：拾阶刚建好代码仓库，还没开工
- 最新证据包：无

## 决策台账（不超过 10 项）
{table}

## 待确认问题
- 无

## 线上资源（阶段 5 起；不含任何密钥）

## 阶段历史
- {today}：拾阶建好代码仓库，交接 PRD、技术方案、评测
""", encoding="utf-8")
    note("新建", "docs/项目状态.md")


def write_build(project: Path, app: Path, name: str, tool: str | None, sync: bool) -> None:
    path = project / "aipm.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    today = dt.date.today().isoformat()
    build = data.get("build") if isinstance(data.get("build"), dict) else {}
    build.update({"path": str(app), "name": name})
    if tool:
        build["tool"] = tool
    build.setdefault("handoff", today)
    if sync:
        build["synced"] = today
    build.setdefault("stage", "0 开发准备")
    data["build"] = build
    data["updated"] = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    note("更新", "aipm.json 的 build")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--project", required=True, type=Path, help="拾阶项目根目录（有 aipm.json 的那一层）")
    parser.add_argument("--app", type=Path, help="MVP 代码仓库目录，默认 <项目>/06-MVP/app")
    parser.add_argument("--tool", help="谁写代码：拾阶 / Claude Code / Codex / 研发团队")
    parser.add_argument("--sync", action="store_true", help="PRD 或技术方案升版后同步")
    args = parser.parse_args()

    project = args.project.expanduser().resolve()
    if not (project / "aipm.json").is_file():
        raise SystemExit(f"{project} 下没有 aipm.json，不是拾阶项目根目录")
    missing = [p for p in ("02-PRD/PRD.md", "04-技术方案/技术方案.md") if not (project / p).is_file()]
    if missing:
        raise SystemExit("还缺：" + "、".join(missing) + "。先做完 PRD 和技术方案。")
    name = json.loads((project / "aipm.json").read_text(encoding="utf-8")).get("project") or project.name
    app = (args.app.expanduser().resolve() if args.app else project / "06-MVP" / "app")
    first = not (app / "AGENTS.md").exists()
    if args.sync and first:
        raise SystemExit(f"{app} 还没装过，先不加 --sync 运行一次")

    if not args.sync:
        for src in files_under(APP_TEMPLATE):
            rel = src.relative_to(APP_TEMPLATE)
            place(src, app / rel, str(rel), overwrite=False)
        readme = app / "README.md"
        if readme.is_file():
            readme.write_text(readme.read_text(encoding="utf-8").replace("{{产品名}}", name), encoding="utf-8")
        (app / "verify.sh").chmod(0o755)
    changed = sync_handoff(project, app, first)
    if not args.sync:
        extract_prompts(project / "02-PRD" / "PRD.md", app)
        install_components(project, app)
        status_file(project, app, name)
        if not (app / ".git").exists():
            subprocess.run(["git", "init", "-q", str(app)], check=True)
            note("新建", ".git（verify.sh 的密钥检查靠 Git 判断哪些文件会进仓库）")
    else:
        log = app / "docs" / "拾阶" / "同步记录.md"
        entry = f"\n## {dt.datetime.now():%Y-%m-%d %H:%M}\n\n" + ("\n".join(f"- {c}" for c in changed) or "- 没有变化") + "\n"
        old = log.read_text(encoding="utf-8") if log.exists() else "# 同步记录\n\n每次拾阶升版后同步，写代码的 AI 读最新一条，增量修改。\n"
        log.write_text(old + entry, encoding="utf-8")
        note("更新", "docs/拾阶/同步记录.md")
    write_build(project, app, name, args.tool, args.sync)

    print(f"MVP 代码仓库：{app}")
    for kind in ("新建", "更新", "保留已有", "提示"):
        if report[kind]:
            print(f"\n{kind}（{len(report[kind])}）：")
            for line in report[kind][:40]:
                print(f"  - {line}")
            if len(report[kind]) > 40:
                print(f"  - ……还有 {len(report[kind]) - 40} 项")


if __name__ == "__main__":
    main()
