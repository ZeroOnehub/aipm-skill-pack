#!/usr/bin/env python3
"""把拾阶项目交接到开发文件夹：第一次建好开发文件夹（规则卡、手册、verify.sh），再建产品文件夹、放进交接资料。

用法：
    python3 install_kit.py --kit <开发文件夹> --name <产品名> --project <拾阶项目根目录> [--components s01,s02,...] [--sync]

- 开发文件夹不存在就新建并 git init；已存在时只补缺的规则文件，改过的不覆盖。
- 产品文件夹在 <开发文件夹>/projects/<产品名>/。研发 PRD、决策台账、补全清单只在第一次放入；
  docs/拾阶交接/ 每次都整体刷新（拾阶自己的资料，编码 AI 只读）。
- --sync：同步交接（PRD 或架构方案升版之后）。研发 PRD 有变化时，旧版存进 docs/PRD/历史/ 再换新版；不碰项目状态。
- 参考组件：默认按 <拾阶项目>/04-AI方案设计/architecture-features.json 的选型复制「必选」组件；--components 指定时以它为准。
- 第一次交接时会跑一次 ./verify.sh <产品名> 阶段0。
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
TEMPLATES = HERE.parent / "templates"
KIT_TEMPLATE = TEMPLATES / "kit"
PRODUCT_TEMPLATE = TEMPLATES / "product"
ARCH_SKILL = HERE.parent.parent / "agent-architecture"
COMPONENTS = ARCH_SKILL / "references" / "components"
COMPONENT_SHARED = ("README.md", "requirements.txt", ".env.example", "common")
SKIP = {".DS_Store", "__pycache__"}

report: dict[str, list[str]] = {"新建": [], "更新": [], "保留已有": [], "提示": []}


def note(kind: str, text: str) -> None:
    report[kind].append(text)


def files_under(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_file() and not SKIP.intersection(path.parts):
            yield path


def place(src: Path, dst: Path, label: str, *, overwrite: bool) -> None:
    """复制一个文件：不存在就新建；存在且相同就跳过；不同时按 overwrite 决定覆盖还是保留。"""
    if dst.exists():
        if filecmp.cmp(src, dst, shallow=False):
            return
        if not overwrite:
            note("保留已有", label)
            return
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        note("更新", label)
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    note("新建", label)


def install_kit(kit: Path) -> None:
    for src in files_under(KIT_TEMPLATE):
        rel = src.relative_to(KIT_TEMPLATE)
        place(src, kit / rel, str(rel), overwrite=False)
    if not (kit / ".git").exists():
        subprocess.run(["git", "init", "-q", str(kit)], check=True)
        note("新建", ".git（verify.sh 的密钥检查要靠 Git 判断哪些文件会进仓库）")


def latest_prompt(design: Path) -> Path | None:
    def version(path: Path) -> int:
        match = re.search(r"-v(\d+)", path.stem)
        return int(match.group(1)) if match else 0
    found = sorted(design.glob("系统提示词-v*.md"), key=version)
    return found[-1] if found else None


def selected_components(project: Path, explicit: str | None) -> list[str]:
    if explicit is not None:
        return [c.strip() for c in explicit.split(",") if c.strip()]
    features_file = project / "04-AI方案设计" / "architecture-features.json"
    if not features_file.exists():
        note("提示", "没有 architecture-features.json（形态不是 Agent，或还没选型），不复制参考组件")
        return []
    sys.path.insert(0, str(ARCH_SKILL / "scripts"))
    from select_components import select  # noqa: PLC0415
    features = json.loads(features_file.read_text(encoding="utf-8"))
    return [d["id"] for d in select(features) if d["decision"] == "必选"]


def install_components(ids: list[str], dest: Path, label: str) -> None:
    if not ids:
        return
    if not COMPONENTS.exists():
        note("提示", f"找不到组件库 {COMPONENTS}，跳过参考组件")
        return
    folders = {p.name[:3]: p for p in COMPONENTS.iterdir() if p.is_dir() and re.match(r"s\d\d_", p.name)}
    unknown = [c for c in ids if c not in folders]
    if unknown:
        raise SystemExit(f"不认识的组件编号：{', '.join(unknown)}")
    for name in COMPONENT_SHARED:
        src = COMPONENTS / name
        targets = files_under(src) if src.is_dir() else [src]
        for f in targets:
            rel = f.relative_to(COMPONENTS)
            place(f, dest / rel, f"{label}/{rel}", overwrite=True)
    for cid in ids:
        for f in files_under(folders[cid]):
            rel = f.relative_to(COMPONENTS)
            place(f, dest / rel, f"{label}/{rel}", overwrite=True)
    existing = sorted(p.name[:3] for p in dest.iterdir() if p.is_dir() and re.match(r"s\d\d_", p.name))
    stale = [c for c in existing if c not in ids]
    if stale:
        note("提示", f"这些组件这一版没选中，参考代码保留没删：{'、'.join(stale)}")


def install_product(kit: Path, name: str, project: Path, components: str | None, sync: bool) -> tuple[Path, bool]:
    if not name or "/" in name or "\\" in name or name.startswith("."):
        raise SystemExit(f"产品名不能为空、不能含斜杠或以点开头：{name!r}")
    package = project / "04-AI方案设计" / "研发交接包"
    needed = [package / "docs" / "PRD" / "PRD.md", package / "交接说明.md"]
    missing = [str(p) for p in needed if not p.exists()]
    if missing:
        raise SystemExit("交接包还没写好，缺：" + "、".join(missing))

    product = kit / "projects" / name
    first_time = not (product / "docs" / "项目状态.md").exists()
    for src in files_under(PRODUCT_TEMPLATE / "docs"):
        rel = src.relative_to(PRODUCT_TEMPLATE)
        place(src, product / rel, f"projects/{name}/{rel}", overwrite=False)

    prd_src, prd_dst = package / "docs" / "PRD" / "PRD.md", product / "docs" / "PRD" / "PRD.md"
    if sync and prd_dst.exists() and not filecmp.cmp(prd_src, prd_dst, shallow=False):
        history = product / "docs" / "PRD" / "历史" / f"PRD-{dt.datetime.now():%Y%m%d-%H%M%S}.md"
        history.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(prd_dst, history)
        note("提示", f"旧版研发 PRD 已存为 docs/PRD/历史/{history.name}")
    place(prd_src, prd_dst, f"projects/{name}/docs/PRD/PRD.md", overwrite=sync)

    once = [
        (package / "docs" / "项目状态.md", product / "docs" / "项目状态.md"),
        (package / "研发补全清单.md", product / "docs" / "阶段文档" / "阶段0-PRD补全清单.md"),
        (TEMPLATES / "product" / "阶段0-是否表.md", product / "docs" / "evidence" / "阶段0" / "是否表.md"),
    ]
    for src, dst in once:
        if src.exists():
            place(src, dst, str(dst.relative_to(kit)), overwrite=False)
        else:
            note("提示", f"交接包里没有 {src.name}")

    handoff = product / "docs" / "拾阶交接"
    design = project / "04-AI方案设计"
    refresh = [
        (package / "交接说明.md", "交接说明.md"),
        (design / "架构方案.md", "架构方案.md"),
        (latest_prompt(design), "系统提示词.md"),
        (design / "迭代记录.md", "迭代记录.md"),
        (project / "02-PRD" / "PRD.md", "需求原文-拾阶PRD.md"),
    ]
    for src, target in refresh:
        if src is not None and src.exists():
            place(src, handoff / target, f"projects/{name}/docs/拾阶交接/{target}", overwrite=True)

    install_components(selected_components(project, components), handoff / "参考组件", f"projects/{name}/docs/拾阶交接/参考组件")
    return product, first_time


def run_verify(kit: Path, name: str) -> str:
    result = subprocess.run(["bash", "verify.sh", name, "阶段0"], cwd=kit, capture_output=True, text=True)
    lines = [l for l in result.stdout.splitlines() if l.startswith(("是否表第", "总判定"))]
    return "\n".join(lines) or result.stdout[-800:]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--kit", required=True, help="开发文件夹")
    parser.add_argument("--name", required=True, help="产品名（产品文件夹名）")
    parser.add_argument("--project", required=True, help="拾阶项目根目录（有 aipm.json 的那个）")
    parser.add_argument("--components", help="逗号分隔的组件编号，如 s01,s02,s04；不给就按架构方案的选型")
    parser.add_argument("--sync", action="store_true", help="同步交接：PRD 或架构方案升版之后用")
    args = parser.parse_args()

    kit, project = Path(args.kit).expanduser().resolve(), Path(args.project).expanduser().resolve()
    if not (project / "aipm.json").exists():
        raise SystemExit(f"{project} 下没有 aipm.json，不是拾阶项目")
    kit.mkdir(parents=True, exist_ok=True)
    install_kit(kit)
    product, first_time = install_product(kit, args.name, project, args.components, args.sync)

    for kind, items in report.items():
        if items:
            print(f"{kind}（{len(items)}）：")
            for item in items:
                print(f"  - {item}")
    if first_time and not args.sync:
        print("\nverify.sh 阶段0：")
        print(run_verify(kit, args.name))
    print("\n写进 aipm.json 的 build 字段：")
    print(json.dumps({"path": str(product), "kit": str(kit), "name": args.name,
                      "handoff": dt.date.today().isoformat()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
