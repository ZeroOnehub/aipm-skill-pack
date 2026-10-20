#!/usr/bin/env bash
# 安装 AIPM Skill Pack。
#
#   ./install.sh <skills 目录>          把每个 skill 链接进去，例如 ~/.claude/skills、~/.codex/skills
#   ./install.sh --workspace <工作区>   给 AIPM 工坊 / DeepSeek Harness 的工作区建 .dsh/skills 链接
#
# 只建符号链接，不复制文件；目标位置已有同名的真实目录时跳过，不覆盖。
set -euo pipefail

PACK="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/skills"

usage() {
  sed -n '2,7p' "$0" | sed 's/^# \{0,1\}//'
  exit 1
}

[ $# -ge 1 ] || usage

if [ "$1" = "--workspace" ]; then
  [ $# -eq 2 ] || usage
  ws="${2/#\~/$HOME}"
  [ -d "$ws" ] || { echo "工作区不存在：$ws" >&2; exit 1; }
  link="$ws/.dsh/skills"
  if [ -e "$link" ] && [ ! -L "$link" ]; then
    echo "$link 已经是一个真实目录，没有改动。请手动处理后再运行。" >&2
    exit 1
  fi
  mkdir -p "$ws/.dsh"
  ln -sfn "$PACK" "$link"
  echo "已链接：$link -> $PACK"
  exit 0
fi

target="${1/#\~/$HOME}"
mkdir -p "$target"
added=0; skipped=0
for dir in "$PACK"/*/; do
  name="$(basename "$dir")"
  dest="$target/$name"
  if [ -e "$dest" ] && [ ! -L "$dest" ]; then
    echo "跳过 $name：$dest 已存在且不是本仓库的链接"
    skipped=$((skipped + 1))
    continue
  fi
  ln -sfn "${dir%/}" "$dest"
  added=$((added + 1))
done
echo "完成：链接 $added 个 skill 到 $target，跳过 $skipped 个。"
