#!/usr/bin/env python3
"""跑评测集：每道题 × 每个候选模型 × N 次，代码判定 + 评审模型判定，输出原始记录和汇总表。

用法：
    python3 run_eval.py <评测集目录> --dry-run
    python3 run_eval.py <评测集目录> [--models a,b] [--runs 3] [--cases T01,T02] [--out <结果目录>]
    python3 run_eval.py <评测集目录> --app-url http://127.0.0.1:8000/api/_eval   # MVP 联调验收：走产品的真实链路

评测集目录里放：
    models.json   候选模型和评审模型（接口地址、模型名、Key 所在的环境变量名、单价）
    cases.jsonl   一行一道题
    prompts/      提示词模板，用 {{区块.字段}} 引用题目里的 vars

只用 Python 标准库；接口是 OpenAI 兼容的 /chat/completions。Key 只从环境变量读，不写进任何文件。
--dry-run 只检查格式、渲染提示词、看 Key 有没有设置，不调模型。
每题跑 N 次（默认 3），N 次都过才算过；任何一次碰了红线检查就记红线。
--app-url：不直接调模型，而是把每道题 POST 给产品的评测入口（请求体 {"id", "stage", "user", "vars"}），
入口跑完整条真实链路后返回 {"output": "...", "tool_calls": [{"name": ...}], "tokens_in", "tokens_out", "cost"}（后四项可省），
判定规则和直接调模型时完全一样。
结果写到 <评测集目录>/../结果/<时间>/：raw.jsonl（每次运行的完整记录）和 汇总.md。
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PLACEHOLDER = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
CHECK_TYPES = {
    "contains", "contains_any", "contains_all", "not_contains", "not_contains_any", "regex", "not_regex",
    "json_valid", "json_path_equals", "json_sum", "count", "tool_called", "tool_not_called", "min_chars", "max_chars",
}
MAX_TURNS = 8


# ---------- 读文件 ----------

def load_models(root: Path) -> tuple[dict[str, dict], str | None]:
    data = json.loads((root / "models.json").read_text(encoding="utf-8"))
    models = {}
    for m in data.get("models", []):
        for key in ("name", "base_url", "model", "key_env"):
            if not m.get(key):
                raise SystemExit(f"models.json 里有模型缺 {key}：{m}")
        models[m["name"]] = m
    return models, data.get("judge")


def load_cases(root: Path) -> list[dict]:
    cases = []
    for n, line in enumerate((root / "cases.jsonl").read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("//"):
            continue
        try:
            case = json.loads(line)
        except json.JSONDecodeError as error:
            raise SystemExit(f"cases.jsonl 第 {n} 行不是合法 JSON：{error}") from None
        case["_line"] = n
        cases.append(case)
    return cases


# ---------- 渲染 ----------

def lookup(vars_: dict, path: str):
    if path in vars_:
        return vars_[path]
    node = vars_
    for part in re.split(r"\.|\[(\d+)\]", path):
        if part in (None, ""):
            continue
        if isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
        elif isinstance(node, dict) and part in node:
            node = node[part]
        else:
            raise KeyError(path)
    return node


def render(template: str, vars_: dict) -> tuple[str, list[str]]:
    missing: list[str] = []

    def sub(match: re.Match) -> str:
        try:
            value = lookup(vars_, match.group(1))
        except KeyError:
            missing.append(match.group(1))
            return match.group(0)
        return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
    return PLACEHOLDER.sub(sub, template), missing


def system_prompt(root: Path, case: dict) -> tuple[str, list[str]]:
    if "system_text" in case:
        text = case["system_text"]
    elif "system" in case:
        path = root / case["system"]
        if not path.exists():
            raise SystemExit(f"{case['id']}：找不到提示词文件 {case['system']}")
        text = path.read_text(encoding="utf-8")
    else:
        text = ""
    return render(text, case.get("vars", {}))


def tool_specs(case: dict) -> list[dict]:
    specs = []
    for name, tool in case.get("tools", {}).items():
        specs.append({"type": "function", "function": {
            "name": name,
            "description": tool.get("description", name),
            "parameters": tool.get("parameters", {"type": "object", "properties": {"query": {"type": "string"}}}),
        }})
    return specs


def tool_reply(case: dict, name: str, arguments: str) -> str:
    tool = case.get("tools", {}).get(name)
    if tool is None:
        return json.dumps({"error": f"没有这个工具：{name}"}, ensure_ascii=False)
    returns = tool.get("returns", "")
    if isinstance(returns, dict):
        for rule in returns.get("match", []):
            if rule.get("if_contains", "") in arguments:
                return rule.get("return", "")
        return returns.get("default", "")
    return returns if isinstance(returns, str) else json.dumps(returns, ensure_ascii=False)


# ---------- 调接口 ----------

def chat(model: dict, messages: list[dict], tools: list[dict] | None, json_mode: bool) -> dict:
    key = os.environ.get(model["key_env"], "")
    if not key:
        raise RuntimeError(f"环境变量 {model['key_env']} 没有设置")
    body: dict = {"model": model["model"], "messages": messages, "temperature": model.get("temperature", 0.7)}
    body.update(model.get("extra", {}))
    if tools:
        body["tools"] = tools
    if json_mode and model.get("json_mode", True):
        body["response_format"] = {"type": "json_object"}
    request = urllib.request.Request(
        model["base_url"].rstrip("/") + "/chat/completions",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=model.get("timeout", 180)) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")[:300]
            if error.code in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(2 ** (attempt + 1))
                continue
            raise RuntimeError(f"HTTP {error.code}：{detail}") from None
        except (urllib.error.URLError, TimeoutError) as error:
            if attempt < 2:
                time.sleep(2 ** (attempt + 1))
                continue
            raise RuntimeError(f"连接失败：{error}") from None
    raise RuntimeError("重试后仍失败")


def run_once(root: Path, case: dict, model: dict) -> dict:
    system, _ = system_prompt(root, case)
    user, _ = render(case["user"], case.get("vars", {}))
    messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": user}]
    tools = tool_specs(case)
    calls: list[dict] = []
    usage = {"in": 0, "out": 0}
    started = time.monotonic()
    output = ""
    for _ in range(MAX_TURNS):
        reply = chat(model, messages, tools or None, case.get("response_format") == "json")
        u = reply.get("usage") or {}
        usage["in"] += u.get("prompt_tokens", 0)
        usage["out"] += u.get("completion_tokens", 0)
        message = reply["choices"][0]["message"]
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            output = message.get("content") or ""
            break
        messages.append({"role": "assistant", "content": message.get("content") or "", "tool_calls": tool_calls})
        for call in tool_calls:
            name = call["function"]["name"]
            arguments = call["function"].get("arguments", "")
            calls.append({"name": name, "arguments": arguments})
            messages.append({"role": "tool", "tool_call_id": call.get("id", name), "content": tool_reply(case, name, arguments)})
    else:
        output = "[超过最大工具轮数，没有产出最终回答]"
    cost = (usage["in"] * model.get("price_in", 0) + usage["out"] * model.get("price_out", 0)) / 1_000_000
    return {"output": output, "tool_calls": calls, "latency_ms": int((time.monotonic() - started) * 1000),
            "tokens_in": usage["in"], "tokens_out": usage["out"], "cost": round(cost, 5)}


def run_app(root: Path, case: dict, url: str) -> dict:
    user, _ = render(case["user"], case.get("vars", {}))
    body = {"id": case["id"], "stage": case.get("stage"), "user": user, "vars": case.get("vars", {})}
    request = urllib.request.Request(url, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=case.get("timeout", 600)) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"HTTP {error.code}：{error.read().decode('utf-8', 'replace')[:300]}") from None
    except (urllib.error.URLError, TimeoutError) as error:
        raise RuntimeError(f"连接失败：{error}") from None
    return {"output": data.get("output", ""), "tool_calls": data.get("tool_calls", []),
            "latency_ms": int((time.monotonic() - started) * 1000), "tokens_in": data.get("tokens_in", 0),
            "tokens_out": data.get("tokens_out", 0), "cost": data.get("cost", 0)}


# ---------- 判定 ----------

def parse_json(text: str):
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if fence:
        text = fence.group(1)
    start = min([i for i in (text.find("{"), text.find("[")) if i >= 0], default=-1)
    if start < 0:
        raise ValueError("没有找到 JSON")
    return json.JSONDecoder().raw_decode(text[start:])[0]


def json_values(data, path: str) -> list:
    nodes = [data]
    for part in re.findall(r"[^.\[\]]+|\[\*\]|\[\d+\]", path):
        next_nodes = []
        for node in nodes:
            if part == "[*]" and isinstance(node, list):
                next_nodes.extend(node)
            elif part.startswith("[") and isinstance(node, list):
                index = int(part[1:-1])
                if index < len(node):
                    next_nodes.append(node[index])
            elif isinstance(node, dict) and part in node:
                next_nodes.append(node[part])
        nodes = next_nodes
    return nodes


def check(c: dict, run: dict) -> tuple[bool, str]:
    text = run["output"]
    kind = c["type"]
    names = [call["name"] for call in run["tool_calls"]]
    if kind == "contains":
        return c["value"] in text, f"包含「{c['value']}」"
    if kind == "contains_any":
        return any(v in text for v in c["values"]), f"包含其一：{'、'.join(c['values'])}"
    if kind == "contains_all":
        lost = [v for v in c["values"] if v not in text]
        return not lost, "全部包含" + (f"（缺：{'、'.join(lost)}）" if lost else "")
    if kind == "not_contains":
        return c["value"] not in text, f"不含「{c['value']}」"
    if kind == "not_contains_any":
        hit = [v for v in c["values"] if v in text]
        return not hit, "都不含" + (f"（出现：{'、'.join(hit)}）" if hit else "")
    if kind == "regex":
        return re.search(c["pattern"], text, re.S) is not None, f"匹配 /{c['pattern']}/"
    if kind == "not_regex":
        return re.search(c["pattern"], text, re.S) is None, f"不匹配 /{c['pattern']}/"
    if kind == "count":
        n = text.count(c["value"])
        ok = n >= c.get("min", 0) and ("max" not in c or n <= c["max"])
        return ok, f"「{c['value']}」出现 {n} 次（要求 {c.get('min', 0)}–{c.get('max', '不限')}）"
    if kind == "min_chars":
        return len(text) >= c["value"], f"字数 {len(text)} ≥ {c['value']}"
    if kind == "max_chars":
        return len(text) <= c["value"], f"字数 {len(text)} ≤ {c['value']}"
    if kind == "tool_called":
        return c["name"] in names, f"调用了 {c['name']}"
    if kind == "tool_not_called":
        return c["name"] not in names, f"没调用 {c['name']}"
    try:
        data = parse_json(text)
    except ValueError as error:
        return False, f"输出不是合法 JSON：{error}"
    if kind == "json_valid":
        return True, "合法 JSON"
    values = json_values(data, c["path"])
    if kind == "json_path_equals":
        return values == [c["value"]], f"{c['path']} = {c['value']}（实际：{values}）"
    if kind == "json_sum":
        total = sum(v for v in values if isinstance(v, (int, float)))
        return total == c["equals"], f"{c['path']} 之和 = {c['equals']}（实际：{total}）"
    return False, f"不认识的检查类型 {kind}"


def judge(root: Path, case: dict, run: dict, judge_model: dict | None, tested: str) -> tuple[bool | None, str]:
    if judge_model is None:
        return None, "没有配置评审模型，需人工判"
    if judge_model["name"] == tested:
        return None, "评审模型和被测模型相同，需人工判"
    prompt = (
        "你是评测评审，只判断，不改写。按评分标准判断被测输出是否通过。\n"
        f"## 任务\n{case.get('task', case['user'])}\n## 评分标准\n{case['judge']}\n## 被测输出\n{run['output']}\n"
        '只输出 JSON：{"pass": true 或 false, "reason": "一句话理由"}'
    )
    try:
        reply = chat(judge_model, [{"role": "user", "content": prompt}], None, True)
        verdict = parse_json(reply["choices"][0]["message"].get("content") or "")
        return bool(verdict.get("pass")), f"评审：{verdict.get('reason', '')}"
    except (RuntimeError, ValueError, KeyError) as error:
        return None, f"评审失败，需人工判：{error}"


def grade(root: Path, case: dict, run: dict, judge_model: dict | None, tested: str) -> dict:
    results = []
    for c in case.get("checks", []):
        ok, detail = check(c, run)
        results.append({"label": c.get("label", c["type"]), "ok": ok, "detail": detail, "redline": bool(c.get("redline"))})
    if case.get("judge"):
        ok, detail = judge(root, case, run, judge_model, tested)
        results.append({"label": "评审模型", "ok": ok, "detail": detail, "redline": False})
    if any(r["ok"] is False for r in results):
        verdict = "不过"
    elif any(r["ok"] is None for r in results):
        verdict = "待人工"
    else:
        verdict = "过"
    return {"verdict": verdict, "checks": results, "redline": any(r["redline"] and r["ok"] is False for r in results)}


# ---------- 主流程 ----------

def validate(root: Path, cases: list[dict], models: dict, judge_name: str | None, chosen: list[str]) -> int:
    problems = 0
    ids = set()
    for case in cases:
        where = f"第 {case['_line']} 行 {case.get('id', '（没有 id）')}"
        for key in ("id", "user"):
            if key not in case:
                print(f"问题：{where} 缺 {key}")
                problems += 1
        if case.get("id") in ids:
            print(f"问题：{where} 编号重复")
            problems += 1
        ids.add(case.get("id"))
        if not case.get("checks") and not case.get("judge"):
            print(f"问题：{where} 没有 checks 也没有 judge，无法判定")
            problems += 1
        for c in case.get("checks", []):
            if c.get("type") not in CHECK_TYPES:
                print(f"问题：{where} 不认识的检查类型 {c.get('type')}")
                problems += 1
        if "user" in case:
            system, missing = system_prompt(root, case)
            _, missing_user = render(case["user"], case.get("vars", {}))
            for name in missing + missing_user:
                print(f"问题：{where} 提示词引用了 {{{{{name}}}}}，vars 里没有")
                problems += 1
            print(f"{case.get('id')}：{case.get('stage', '')} / {case.get('type', '')}，提示词 {len(system)} 字，"
                  f"{len(case.get('checks', []))} 条检查{'＋评审' if case.get('judge') else ''}，工具 {len(case.get('tools', {}))} 个")
    types = sorted({c.get("type", "未标") for c in cases})
    print(f"\n共 {len(cases)} 题；题型：{'、'.join(types)}")
    for name in chosen + ([judge_name] if judge_name else []):
        model = models.get(name)
        if model is None:
            print(f"问题：models.json 里没有 {name}")
            problems += 1
            continue
        if name == "app":
            print(f"被测对象：产品评测入口 {model['model']}")
            continue
        state = "已设置" if os.environ.get(model["key_env"]) else "未设置"
        print(f"模型 {name}（{model['model']}）：环境变量 {model['key_env']} {state}")
    print(f"\n{'检查通过' if problems == 0 else f'有 {problems} 个问题'}")
    return problems


def summarize(out: Path, cases: list[dict], records: list[dict], chosen: list[str], runs: int) -> str:
    lines = [f"# 评测汇总 {out.name}", "", f"每题跑 {runs} 次，{runs} 次都过才算过。", "",
             f"| 模型 | {runs} 次全过 | 红线命中 | 待人工 | 平均时延 | 平均每题成本 |", "|---|---|---|---|---|---|"]
    by = {(r["case"], r["model"]): [] for r in records}
    for r in records:
        by[(r["case"], r["model"])].append(r)
    def verdict(r: dict) -> str:
        return r.get("grade", {}).get("verdict", "出错")

    for name in chosen:
        mine = [by.get((c["id"], name), []) for c in cases]
        passed = sum(1 for rs in mine if rs and all(verdict(r) == "过" for r in rs))
        red = sum(1 for rs in mine if any(r.get("grade", {}).get("redline") for r in rs))
        manual = sum(1 for rs in mine if rs and all(verdict(r) in ("过", "待人工") for r in rs)
                     and any(verdict(r) == "待人工" for r in rs))
        flat = [r for rs in mine for r in rs if "error" not in r]
        latency = sum(r["latency_ms"] for r in flat) / len(flat) / 1000 if flat else 0
        cost = sum(r["cost"] for r in flat) / len(cases) if cases else 0
        lines.append(f"| {name} | {passed} / {len(cases)} | {red} | {manual} | {latency:.1f} s | {cost:.4f} |")
    lines += ["", "## 逐题", "", "| 编号 | 环节 | 题型 | " + " | ".join(chosen) + " |", "|---|---|---|" + "---|" * len(chosen)]
    for c in cases:
        cells = []
        for name in chosen:
            marks = "".join({"过": "✓", "不过": "✗", "待人工": "?"}.get(r["grade"]["verdict"], "!") if "grade" in r else "!"
                            for r in by.get((c["id"], name), []))
            if any(r.get("grade", {}).get("redline") for r in by.get((c["id"], name), [])):
                marks += " 红线"
            cells.append(marks)
        lines.append(f"| {c['id']} | {c.get('stage', '')} | {c.get('type', '')} | " + " | ".join(cells) + " |")
    lines += ["", "✓ 过　✗ 不过　? 待人工判　! 调用出错", "", "## 没过的检查", ""]
    for r in records:
        if "error" in r:
            lines.append(f"- {r['case']} · {r['model']} · 第 {r['run']} 次：调用出错 {r['error']}")
            continue
        for c in r["grade"]["checks"]:
            if c["ok"] is not True:
                flag = "【红线】" if c["redline"] and c["ok"] is False else ""
                lines.append(f"- {r['case']} · {r['model']} · 第 {r['run']} 次：{flag}{c['label']}：{c['detail']}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("root", type=Path, help="评测集目录")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--models", help="逗号分隔；默认 models.json 里全部候选")
    parser.add_argument("--runs", type=int, default=None, help="每题跑几次，默认 3（题目里写了 runs 的以题目为准）")
    parser.add_argument("--cases", help="逗号分隔的题号，只跑这几题")
    parser.add_argument("--out", type=Path, help="结果目录，默认 <评测集目录>/../结果/<时间>")
    parser.add_argument("--app-url", help="产品的评测入口地址；给了就走产品的真实链路，不直接调模型")
    args = parser.parse_args()

    root = args.root.resolve()
    models, judge_name = load_models(root)
    if args.app_url:
        models["app"] = {"name": "app", "model": args.app_url, "key_env": ""}
    cases = load_cases(root)
    if args.cases:
        wanted = {c.strip() for c in args.cases.split(",")}
        cases = [c for c in cases if c.get("id") in wanted]
    if args.app_url:
        chosen = ["app"]
    else:
        chosen = [m.strip() for m in args.models.split(",")] if args.models else [n for n in models if n != judge_name]

    if validate(root, cases, models, judge_name, chosen) and not args.dry_run:
        raise SystemExit("先修好上面的问题再跑。")
    if args.dry_run:
        return
    for name in chosen:
        if name != "app" and not os.environ.get(models[name]["key_env"]):
            raise SystemExit(f"模型 {name} 的环境变量 {models[name]['key_env']} 没有设置。设置方法见评测方案「被测配置」。")

    out = args.out or root.parent / "结果" / dt.datetime.now().strftime("%Y%m%d-%H%M")
    out.mkdir(parents=True, exist_ok=True)
    judge_model = models.get(judge_name) if judge_name else None
    records = []
    with (out / "raw.jsonl").open("w", encoding="utf-8") as raw:
        for case in cases:
            n = args.runs or case.get("runs", 3)
            for name in chosen:
                for i in range(1, n + 1):
                    record = {"case": case["id"], "model": name, "run": i}
                    try:
                        record.update(run_app(root, case, args.app_url) if name == "app" else run_once(root, case, models[name]))
                        record["grade"] = grade(root, case, record, judge_model, name)
                        mark = record["grade"]["verdict"]
                    except RuntimeError as error:
                        record["error"] = str(error)
                        mark = f"出错：{error}"
                    print(f"{case['id']} · {name} · 第 {i}/{n} 次：{mark}", flush=True)
                    raw.write(json.dumps(record, ensure_ascii=False) + "\n")
                    records.append(record)
    summary = summarize(out, cases, records, chosen, args.runs or 3)
    (out / "汇总.md").write_text(summary, encoding="utf-8")
    print(f"\n结果：{out}/汇总.md")


if __name__ == "__main__":
    sys.exit(main())
