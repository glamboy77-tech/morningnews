#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$SCRIPT_DIR"
LOG_DIR="$REPO_DIR/logs"
LOG_FILE="$LOG_DIR/morningnews_$(date +'%Y%m%d').log"

mkdir -p "$LOG_DIR"
exec >>"$LOG_FILE" 2>&1

echo "[INFO] $(date) Starting morningnews job"
cd "$REPO_DIR"

WORKTREE_DIRTY=0
if [ -n "$(git status --porcelain)" ]; then
  WORKTREE_DIRTY=1
  echo "[WARN] Working tree has local changes. Will skip git pull, but will still try to commit only generated outputs."
fi

# 1) 안전하게 원격 동기화 (분기 발생 시 즉시 실패)
if [ "$WORKTREE_DIRTY" -eq 0 ]; then
  git fetch origin
  # origin/main과 fast-forward만 허용
  if ! git pull --ff-only origin main; then
    echo "[ERROR] git pull --ff-only failed (diverged). Aborting."
    exit 1
  fi
else
  echo "[INFO] Skipping git pull because the working tree is dirty."
fi

# 2) 가상환경 활성화/준비
if [ ! -d ".venv" ]; then
  echo "[INFO] Creating venv"
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -r requirements.txt

# 3) 오늘자 결과가 이미 있으면 스킵 (이중실행 방지)
TODAY=$(date +'%Y%m%d')
DONE_MARKER="$REPO_DIR/.run_state/done_${TODAY}.json"
if [ -f "$DONE_MARKER" ] && [ -f "output/morning_news_${TODAY}.html" ]; then
  echo "[INFO] Already generated today (done marker + HTML output). Skipping."
  exit 0
fi

# 4) 실행
python3 main.py

# 4.5) 발행 품질 게이트: done marker와 필수 산출물이 없으면 커밋/푸시 금지
REQUIRED_OUTPUTS=(
  "$DONE_MARKER"
  "output/morning_news_${TODAY}.html"
  "data_cache/rss_${TODAY}.json"
  "data_cache/ai_analysis_${TODAY}.json"
  "data_cache/key_persons_${TODAY}.json"
  "data_cache/trending_keywords_${TODAY}.json"
  "sentiment_cache/sentiment_${TODAY}.json"
)

for path in "${REQUIRED_OUTPUTS[@]}"; do
  if [ ! -s "$path" ]; then
    echo "[ERROR] Required publish output missing or empty: $path"
    echo "[ERROR] Will not commit/push partial or broken outputs."
    exit 1
  fi
done

# 5) 생성 산출물만 선택적으로 커밋/푸시
TARGETS=(
  "index.html"
  "archive.html"
  "output/morning_news_${TODAY}.html"
  "data_cache/rss_${TODAY}.json"
  "data_cache/ai_analysis_${TODAY}.json"
  "data_cache/key_persons_${TODAY}.json"
  "data_cache/trending_keywords_${TODAY}.json"
  "sentiment_cache/sentiment_${TODAY}.json"
)

STAGE_TARGETS=()
for path in "${TARGETS[@]}"; do
  if [ -e "$path" ]; then
    STAGE_TARGETS+=("$path")
  fi
done

if [ "${#STAGE_TARGETS[@]}" -eq 0 ]; then
  echo "[INFO] No generated targets found to stage."
else
  git add -- "${STAGE_TARGETS[@]}"
  if ! git diff --cached --quiet; then
    git commit -m "🗞️ Generate morning news $(date +'%Y-%m-%d')"
    git push origin main
  else
    echo "[INFO] No generated output changes to commit."
  fi
fi

echo "[INFO] $(date) Job finished"
