#!/usr/bin/env bash
# 自检脚本：由脚本而不是 AI 判断五件事（mock 测试 / 密钥排除 / 重启恢复 / 前端构建 / 文件齐全）。
# 用法：./verify.sh [阶段名]     例：./verify.sh 阶段1-1   （提示"权限不够"时在前面加 bash）
# 阶段名：阶段0、阶段1-N、阶段2、阶段3-N、阶段4、阶段5（见 AGENTS.md 第 7 节）。
# 给了阶段名，会把完整输出写到 docs/evidence/<阶段名>/verify-输出.txt。
# 退出码：全部通过或 N/A 为 0；任一"不通过"或"未配置"为 1。
set -u
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
STAGE="${1:-}"
LOG="$(mktemp)"
log() { printf '%s\n' "$*" | tee -a "$LOG"; }
sect() { log ""; log "================ $* ================"; }

R1="未配置"; R2="未配置"; R3="未配置"; R4="N/A（本阶段无正式前端）"; R5=""
NOCODE=0; case "$STAGE" in 阶段0|阶段2) NOCODE=1;; esac   # 无代码阶段：测试和重启检查不适用

log "verify.sh 自检  $(date '+%Y-%m-%d %H:%M:%S')  目录：${ROOT}  阶段：${STAGE:-（未指定）}"

# ---------- 1. mock 自动化测试 ----------
sect "1. mock 自动化测试"
if [ "$NOCODE" -eq 1 ]; then
  R1="N/A（无代码阶段）"
elif [ -d backend/tests ]; then
  PY="$ROOT/backend/.venv/bin/python"; [ -x "$PY" ] || PY="$(command -v python3)"
  T="$(mktemp)"
  (cd backend && MODEL_API_KEY="" "$PY" -m pytest -q 2>&1) > "$T"; RC=$?
  cat "$T" >> "$LOG"
  PASSED="$(grep -Eo '[0-9]+ passed' "$T" | tail -1 | grep -Eo '[0-9]+')"; PASSED="${PASSED:-0}"
  FAILED="$(grep -Eo '[0-9]+ (failed|error)' "$T" | grep -Eo '[0-9]+' | paste -sd+ - | bc 2>/dev/null)"; FAILED="${FAILED:-0}"
  TOTAL=$((PASSED + FAILED))
  if [ "$RC" -eq 0 ] && [ "$PASSED" -gt 0 ]; then R1="通过（${PASSED}/${TOTAL}）"; else R1="不通过（通过 ${PASSED}/${TOTAL}，退出码 ${RC}）"; fi
  rm -f "$T"
else
  log "未找到 backend/tests，跳过后端测试。"
fi
if [ "$NOCODE" -eq 0 ] && [ -f frontend/package.json ] && grep -q '"test"' frontend/package.json; then
  T="$(mktemp)"
  (cd frontend && npm test --silent -- --run 2>&1) > "$T"; RC=$?
  cat "$T" >> "$LOG"
  if [ "$RC" -eq 0 ]; then R1="${R1}；前端测试通过"; else R1="不通过（前端测试退出码 ${RC}）"; fi
  rm -f "$T"
fi
log "结果：$R1"

# ---------- 2. 密钥排除 ----------
sect "2. 密钥排除（扫描会进 git 的文件和构建产物）"
PAT='sk-[A-Za-z0-9]{20,}|AKLT[A-Za-z0-9]{10,}|AKIA[0-9A-Z]{16}|(api[_-]?key|secret|password|token)[[:space:]]*[=:][[:space:]]*["'"'"']?[A-Za-z0-9_-]{20,}'
HITS=0
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  log "问题：这个文件夹不是 Git 仓库，无法判断哪些文件会进仓库。请先执行 git init 并配置 .gitignore。"
  HITS=$((HITS+1))
fi
lsfiles() { git ls-files -z --cached --others --exclude-standard 2>/dev/null; }
ENV_TRACKED="$(git ls-files 2>/dev/null | grep -E '(^|/)\.env(\.[A-Za-z0-9_-]+)?$' | grep -v '\.env\.example$' || true)"
if [ -n "$ENV_TRACKED" ]; then log "问题：以下 .env 文件被 git 跟踪："; log "$ENV_TRACKED"; HITS=$((HITS+1)); else log "通过：没有 .env 文件被 git 跟踪。"; fi
M="$(lsfiles | xargs -0 grep -InE --exclude=verify.sh "$PAT" 2>/dev/null | sed -E 's/([A-Za-z0-9_-]{6})[A-Za-z0-9_-]{8,}/\1******/g' || true)"
if [ -n "$M" ]; then log "问题：会进仓库的文件中发现疑似密钥（已打码）："; log "$M"; HITS=$((HITS+1)); else log "通过：会进仓库的文件中未发现密钥样式字符串。"; fi
BUILDS="frontend/.next frontend/dist frontend/out backend/dist"
for d in $BUILDS; do
  [ -d "$d" ] || continue
  M="$(grep -rIlE "$PAT" "$d" 2>/dev/null || true)"
  if [ -n "$M" ]; then log "问题：构建产物 $d 中发现疑似密钥，文件："; log "$M"; HITS=$((HITS+1)); else log "通过：构建产物 $d 未发现密钥样式字符串。"; fi
done
# 本机 .env 里的真实 Key 值不得出现在任何会进仓库的文件或构建产物里（值本身不打印）
for envf in backend/.env backend/.env.secrets .env frontend/.env.local; do
  [ -f "$envf" ] || continue
  while IFS= read -r line; do
    case "$line" in \#*|"") continue;; esac
    name="${line%%=*}"
    echo "$name" | grep -qiE 'key|secret|token|pass|access' || continue
    val="${line#*=}"; val="${val%\"}"; val="${val#\"}"
    [ "${#val}" -ge 12 ] || continue
    FOUND="$(lsfiles | xargs -0 grep -IlF -- "$val" 2>/dev/null || true)"
    for d in $BUILDS; do [ -d "$d" ] && FOUND="$FOUND $(grep -rIlF -- "$val" "$d" 2>/dev/null || true)"; done
    FOUND="$(echo "$FOUND" | xargs 2>/dev/null || true)"
    if [ -n "$FOUND" ]; then log "问题：$envf 中 ${name} 的值出现在：$FOUND"; HITS=$((HITS+1)); else log "通过：$envf 中 ${name} 的值未出现在会进仓库的文件或构建产物中。"; fi
  done < "$envf"
done
if [ "$HITS" -eq 0 ]; then R2="通过"; else R2="不通过（${HITS} 处问题，见输出）"; fi
log "结果：$R2"

# ---------- 3. 重启恢复 ----------
sect "3. 数据重启恢复（调用 scripts/restart-check.sh）"
if [ "$NOCODE" -eq 1 ]; then
  R3="N/A（无代码阶段）"
elif [ -x scripts/restart-check.sh ]; then
  T="$(mktemp)"; bash scripts/restart-check.sh > "$T" 2>&1; RC=$?
  tee -a "$LOG" < "$T"; rm -f "$T"
  if [ "$RC" -eq 0 ]; then R3="通过"; else R3="不通过（退出码 ${RC}，见输出）"; fi
else
  log "未找到 scripts/restart-check.sh。有可重启的服务时，必须按项目写这个钩子。"
fi
log "结果：$R3"

# ---------- 4. 前端类型检查 / Lint / 生产构建 ----------
sect "4. 前端类型检查 / Lint / 生产构建"
if [ "$NOCODE" -eq 0 ] && [ -f frontend/package.json ]; then
  FAIL=""
  T="$(mktemp)"
  if grep -q '"lint"' frontend/package.json; then (cd frontend && npm run lint 2>&1) >> "$T" || FAIL="$FAIL lint"; fi
  if [ -f frontend/tsconfig.json ]; then (cd frontend && npx tsc --noEmit 2>&1) >> "$T" || FAIL="$FAIL 类型检查"; fi
  if grep -q '"build"' frontend/package.json; then (cd frontend && npm run build 2>&1) >> "$T" || FAIL="$FAIL 生产构建"; fi
  cat "$T" >> "$LOG"; rm -f "$T"
  if [ -z "$FAIL" ]; then R4="通过"; else R4="不通过（失败项：${FAIL}）"; fi
else
  log "本阶段没有正式前端（或无代码阶段）。"
fi
log "结果：$R4"

# ---------- 5. 文件齐全 ----------
sect "5. 文件齐全（AGENTS.md 第 7 节的产出清单）"
MISS=0; NEED=(); EVI=0
case "$STAGE" in
  "") ;;
  阶段0) NEED=(docs/阶段文档/开发计划.md "docs/evidence/$STAGE/是否表.md") ;;
  阶段1-[0-9]*) NEED=("docs/阶段文档/${STAGE}开发文档.md"); EVI=1 ;;
  阶段2) NEED=(docs/设计/风格候选.html docs/设计/设计规范.md "docs/evidence/$STAGE/是否表.md") ;;
  阶段3-[0-9]*) NEED=(docs/设计/设计规范.md "docs/阶段文档/${STAGE}开发文档.md"); EVI=1 ;;
  阶段4) NEED=(docs/阶段文档/验收报告.md); EVI=1 ;;
  阶段5) NEED=(docs/阶段文档/上线方案摘要.md); EVI=1 ;;
  *) log "问题：不认识的阶段名 ${STAGE}（应为 阶段0、阶段1-1、阶段2、阶段3-1、阶段4、阶段5 这类）。"; MISS=$((MISS+1)) ;;
esac
if [ -n "$STAGE" ]; then
  NEED+=(docs/项目状态.md)
  [ "$EVI" -eq 1 ] && NEED+=(README.md "docs/evidence/$STAGE/照着做清单.md" "docs/evidence/$STAGE/是否表.md")
  for f in ${NEED[@]+"${NEED[@]}"}; do
    if [ -s "$f" ]; then log "有：$f"; else log "缺：$f"; MISS=$((MISS+1)); fi
  done
  if [ "$EVI" -eq 1 ]; then
    SHOTS="$(ls "docs/evidence/$STAGE" 2>/dev/null | grep -icE '\.(png|jpe?g)$')"
    if [ "$SHOTS" -gt 0 ]; then log "有：docs/evidence/$STAGE/ 下 $SHOTS 张截图"; else log "缺：docs/evidence/$STAGE/ 下至少一张截图（.png / .jpg）"; MISS=$((MISS+1)); fi
  fi
fi
if [ "$MISS" -gt 0 ]; then R5="不通过（缺 ${MISS} 个文件）"
elif [ -z "$STAGE" ]; then R5="N/A（没给阶段名，不查文件齐全）"
else R5="通过"; fi
log "结果：$R5"

# ---------- 汇总 ----------
sect "汇总（抄进是否表的就是这五行）"
log "是否表第 2 项  mock 测试：      $R1"
log "是否表第 4 项  前端检查与构建： $R4"
log "是否表第 5 项  密钥排除：       $R2"
log "是否表第 6 项  重启后数据恢复： $R3"
log "是否表第 10 项 文件齐全：       $R5"
EXIT=0
for r in "$R1" "$R2" "$R3" "$R4" "$R5"; do case "$r" in 不通过*|未配置*) EXIT=1;; esac; done
if [ "$EXIT" -eq 0 ]; then log "总判定：五项全部通过或不适用。"; else log "总判定：有不通过或未配置项，对应是否表只能填\"否\"。"; fi

if [ -n "$STAGE" ]; then
  mkdir -p "docs/evidence/$STAGE"
  cp "$LOG" "docs/evidence/$STAGE/verify-输出.txt"
  log "完整输出已写入：docs/evidence/$STAGE/verify-输出.txt"
fi
rm -f "$LOG"
exit "$EXIT"
