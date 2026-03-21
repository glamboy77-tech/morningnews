# MorningNews / MorningNews-YouTube 새 서버 이전 가이드

이 문서는 `morningnews` 와 `morningnews-youtube` 를 **이미 복사해 온 현재 상태를 기준으로**,
처음부터 다시 옮기기보다 **점검 → 보정 → 검증** 방식으로 이전을 완료하기 위한 운영 문서입니다.

---

## 1. 권장 전략

### 결론
- **전부 다시 복사할 필요는 없습니다.**
- 먼저 현재 복사본을 기준으로 아래를 점검합니다.
  1. 파일/폴더 누락 여부
  2. 절대경로 잔존 여부
  3. `.env` / `secrets` / OAuth 파일 존재 여부
  4. Python / ffmpeg / git 권한 준비 여부
  5. 수동 실행 성공 여부
  6. systemd 등록 및 자동화 검증

### 왜 이 방식이 더 안전한가
- 이미 SFTP로 핵심 디렉터리를 가져온 상태라면 대용량 복사 자체는 끝난 상태입니다.
- 실제 장애 원인은 보통 복사 자체보다 다음 항목에서 발생합니다.
  - 하드코딩된 절대경로
  - 환경변수 누락
  - 인증 파일 누락
  - `git pull/push` 권한 부족
  - `ffmpeg` / Python 의존성 누락
  - systemd 경로 불일치

---

## 2. 현재 확인된 구조 요약

### `morningnews`
- 진입 스크립트: `run_morningnews.sh`
- 주요 동작:
  - git fetch/pull
  - `.venv` 생성
  - `pip install -r requirements.txt`
  - `python3 main.py`
  - 산출물 git commit/push
- 주요 산출물:
  - `output/morning_news_YYYYMMDD.html`
  - `index.html`
  - `archive.html`
  - `scripts/youtube_tts_YYYYMMDD.txt`
  - `scripts/shorts_YYYYMMDD.json`
  - `.run_state/done_YYYYMMDD.json`

### `morningnews-youtube`
- 진입 스크립트: `bin/run_daily.sh`
- 주요 동작:
  - 외부 스크립트(`MORNINGNEWS_SCRIPTS_DIR`) 읽기
  - TTS / SRT / MP4 / 썸네일 / 메타 생성
  - 롱폼 publish
  - 쇼츠 JSON이 있으면 쇼츠 빌드/업로드 추가 수행
- 주요 입력:
  - `youtube_tts_YYYYMMDD.txt`
  - `shorts_YYYYMMDD.json` 또는 `youtube_shorts_YYYYMMDD.json`

---

## 3. 이전 대상 체크리스트

아래는 **필수 이관 대상**입니다.

### 필수 디렉터리
- [ ] `morningnews/`
- [ ] `morningnews-youtube/`

### 필수 환경/인증 파일
- [ ] `morningnews/.env`
- [ ] `morningnews-youtube/.env`
- [ ] `morningnews-youtube/secrets/client_secret.json`
- [ ] `morningnews-youtube/secrets/token.json`
- [ ] 필요 시 `vapid_private.pem`
- [ ] 필요 시 Google Cloud TTS 인증 JSON

### 선택적 이관 항목
운영 연속성을 위해 함께 가져오면 좋습니다.

- [ ] `morningnews/.run_state/`
- [ ] `morningnews/data_cache/`
- [ ] `morningnews/sentiment_cache/`
- [ ] `morningnews-youtube/work/`
- [ ] `morningnews-youtube/logs/`

---

## 4. 새 서버 권장 디렉터리 구조

둘 중 하나를 선택합니다.

### 옵션 A. 기존 스타일 유지
- `/home/<user>/morningnews`
- `/home/<user>/morningnews-youtube`

### 옵션 B. 운영용 표준 경로
- `/opt/morningnews`
- `/opt/morningnews-youtube`

> 중요한 것은 절대경로 자체보다, **systemd unit / .env / 인증 파일 / 스크립트가 모두 같은 기준 경로를 보도록 통일**하는 것입니다.

---

## 5. 코드 점검 결과

### 이미 보정된 부분
- `morningnews-youtube/bin/run_daily.sh` 는 저장소 기준 상대경로 계산을 잘 사용합니다.
- `morningnews-youtube` 내부 코드는 `MORNINGNEWS_SCRIPTS_DIR` 를 지원하므로 새 서버 경로 적응성이 좋습니다.

### 이번 점검에서 발견한 주요 서버 종속값

#### 1) `morningnews/run_morningnews.sh`
기존에는 아래와 같이 절대경로가 하드코딩되어 있었습니다.

```bash
REPO_DIR="/home/glamboy77/morningnews"
```

이번 작업에서 다음처럼 **스크립트 위치 기준 상대경로 방식**으로 수정했습니다.

```bash
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$SCRIPT_DIR"
```

즉, 이 스크립트는 이제 어느 경로로 옮겨도 그 경로 기준으로 동작합니다.

#### 2) `morningnews-youtube/.env`
현재 아래 값이 남아 있을 가능성이 큽니다.

```env
GOOGLE_APPLICATION_CREDENTIALS=/home/glamboy77/secrets/....json
```

이 값은 새 서버 경로에 맞게 반드시 수정해야 합니다.

---

## 6. 환경변수 체크리스트

### `morningnews/.env`
최소 확인:

- [ ] `GEMINI_API_KEY`
- [ ] `OPENAI_API_KEY`
- [ ] `TELEGRAM_BOT_TOKEN`
- [ ] `TELEGRAM_CHAT_ID`
- [ ] `WEATHER_LOCATION`

선택 확인:

- [ ] `GEMINI_MODEL_FLASH`
- [ ] `GEMINI_MODEL_LITE`
- [ ] `GEMINI_MODEL_PRO`
- [ ] `OPENAI_MODEL_TTS`
- [ ] `SERVER_IP`
- [ ] `VAPID_PRIVATE_KEY`
- [ ] `VAPID_PUBLIC_KEY`
- [ ] `VAPID_EMAIL`

### `morningnews-youtube/.env`
최소 확인:

- [ ] `TELEGRAM_BOT_TOKEN`
- [ ] `TELEGRAM_CHAT_ID`
- [ ] `GOOGLE_APPLICATION_CREDENTIALS`

선택 확인:

- [ ] `MORNINGNEWS_SCRIPTS_DIR`
- [ ] `YOUTUBE_CLIENT_SECRET`
- [ ] `YOUTUBE_TOKEN_FILE`

---

## 7. 시스템 패키지 준비

새 서버에 최소한 아래가 필요합니다.

- [ ] `python3`
- [ ] `python3-venv`
- [ ] `pip`
- [ ] `git`
- [ ] `curl`
- [ ] `ffmpeg`
- [ ] `ffprobe`

설치 예시(Ubuntu/Debian):

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git curl ffmpeg
```

---

## 8. Python 환경 준비

### morningnews
```bash
cd /경로/morningnews
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### morningnews-youtube
```bash
cd /경로/morningnews-youtube
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> 운영 안정성 관점에서는 매일 `pip install -r requirements.txt` 를 돌리기보다,
> 배포 시에만 재설치하는 방식이 더 안전합니다.

---

## 9. Git / SSH 권한 점검

`morningnews/run_morningnews.sh` 는 실행 중 아래 작업을 수행합니다.
- `git fetch origin`
- `git pull --ff-only origin main`
- `git push origin main`

따라서 실행 계정에 **원격 저장소 push 권한**이 있어야 합니다.

확인 항목:
- [ ] SSH key 또는 deploy key 등록
- [ ] `git remote -v` 정상 확인
- [ ] 비대화형 인증 가능
- [ ] `git pull` / `git push` 테스트 완료

---

## 10. 수동 검증 절차

자동 등록 전에 반드시 수동 실행을 먼저 합니다.

### 10-1. morningnews 수동 실행
```bash
cd /경로/morningnews
bash run_morningnews.sh
```

확인 포인트:
- [ ] 로그 파일 생성: `logs/morningnews_YYYYMMDD.log`
- [ ] HTML 생성: `output/morning_news_YYYYMMDD.html`
- [ ] 루트 페이지 갱신: `index.html`, `archive.html`
- [ ] 유튜브 대본 생성: `scripts/youtube_tts_YYYYMMDD.txt`
- [ ] 쇼츠 JSON 생성: `scripts/shorts_YYYYMMDD.json` 또는 legacy 파일
- [ ] done marker 생성: `.run_state/done_YYYYMMDD.json`

### 10-2. morningnews-youtube 수동 실행
```bash
cd /경로/morningnews-youtube
bash bin/run_daily.sh
```

확인 포인트:
- [ ] `audio/voice_YYYYMMDD.*`
- [ ] `subs/voice_YYYYMMDD.srt`
- [ ] `video/briefing_YYYYMMDD.mp4`
- [ ] `assets/thumbnails/thumbnail_YYYYMMDD.png`
- [ ] `work/youtube_meta_YYYYMMDD.json`
- [ ] publish 성공 또는 recoverable 실패 코드 확인

---

## 11. systemd 등록 순서

권장 실행 순서:
- `morningnews.timer` → 매일 **06:00 KST**
- `morningnews-youtube.timer` → 매일 **06:15 KST**

> 기존 06:10도 가능하지만, LLM 호출/네트워크 지연을 감안하면 06:15가 더 안전합니다.

배포 템플릿은 아래 경로를 참고합니다.

- `morningnews/deploy/systemd/morningnews.service`
- `morningnews/deploy/systemd/morningnews.timer`
- `morningnews/deploy/systemd/morningnews-youtube.service`
- `morningnews/deploy/systemd/morningnews-youtube.timer`

배포 예시:

```bash
sudo cp morningnews/deploy/systemd/morningnews.service /etc/systemd/system/
sudo cp morningnews/deploy/systemd/morningnews.timer /etc/systemd/system/
sudo cp morningnews/deploy/systemd/morningnews-youtube.service /etc/systemd/system/
sudo cp morningnews/deploy/systemd/morningnews-youtube.timer /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable --now morningnews.timer
sudo systemctl enable --now morningnews-youtube.timer
```

---

## 12. 운영 검증 명령어

```bash
systemctl list-timers --all | grep morningnews
systemctl status morningnews.service
systemctl status morningnews-youtube.service
journalctl -u morningnews.service -n 100 --no-pager
journalctl -u morningnews-youtube.service -n 100 --no-pager
```

---

## 13. 장애 시 우선 점검 포인트

### morningnews 실패 시
1. `.env` 누락 또는 API 키 누락
2. `git pull` / `git push` 인증 실패
3. Python 패키지 설치 실패
4. RSS/LLM API 장애

### morningnews-youtube 실패 시
1. `MORNINGNEWS_SCRIPTS_DIR` 경로 오설정
2. `youtube_tts_YYYYMMDD.txt` 미생성
3. `GOOGLE_APPLICATION_CREDENTIALS` 경로 오류
4. `secrets/client_secret.json`, `secrets/token.json` 누락
5. `ffmpeg` / `ffprobe` 미설치

---

## 14. 최종 이전 완료 체크리스트

- [ ] 두 프로젝트 디렉터리 배치 완료
- [ ] `.env` / OAuth / 인증 파일 복원 완료
- [ ] 절대경로 점검 완료
- [ ] Python venv 및 requirements 설치 완료
- [ ] `ffmpeg` 설치 완료
- [ ] git pull/push 권한 확인 완료
- [ ] `morningnews` 수동 실행 성공
- [ ] `morningnews-youtube` 수동 실행 성공
- [ ] systemd timer 등록 완료
- [ ] `list-timers`, `journalctl` 검증 완료
