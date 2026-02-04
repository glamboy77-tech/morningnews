#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/home/glamboy77/morningnews"
LOG_DIR="$REPO_DIR/logs"
LOG_FILE="$LOG_DIR/morningnews_$(date +'%Y%m%d').log"

mkdir -p "$LOG_DIR"
exec >>"$LOG_FILE" 2>&1

echo "[INFO] $(date) Starting morningnews job"
cd "$REPO_DIR"

# 1) 안전하게 원격 동기화 (분기 발생 시 즉시 실패)
git fetch origin
# origin/main과 fast-forward만 허용
if ! git pull --ff-only origin main; then
  echo "[ERROR] git pull --ff-only failed (diverged). Aborting."
  exit 1
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
if [ -f "output/morning_news_${TODAY}.html" ]; then
  echo "[INFO] Already generated today. Skipping."
  exit 0
fi

# 4) 실행
python3 main.py

# 5) 변경사항 커밋/푸시
if ! git diff --quiet || ! git diff --staged --quiet; then
  git add .
  if ! git diff --cached --quiet; then
    git commit -m "🗞️ Generate morning news $(date +'%Y-%m-%d')"
    git push origin main
  fi
else
  echo "[INFO] No changes to commit."
fi

echo "[INFO] $(date) Job finished"
