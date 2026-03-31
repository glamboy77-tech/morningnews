# 모닝뉴스 자동화 설정 가이드

이 문서는 모닝뉴스봇의 자동화 설정에 대한 가이드입니다.

> **현재 시스템은 systemd 타이머를 사용하여 실행됩니다.**
> GitHub Actions는 백업/수동 실행용으로만 설정되어 있습니다.

## 1. GitHub Repository 생성

1. GitHub에서 새 저장소를 생성합니다
2. 로컬 프로젝트를 GitHub에 푸시합니다:

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
git push -u origin main
```

## 2. GitHub Secrets 설정

GitHub 저장소의 Settings > Secrets and variables > Actions > New repository secret 에서 다음 환경 변수들을 설정하세요:

### 필수 설정

#### Gemini API 설정
- `GEMINI_API_KEY`: Google Gemini API 키

#### VAPID 키 설정 (PWA Push)
- `VAPID_PRIVATE_KEY`: VAPID 개인 키 (전체 PEM 내용)
  ```
  -----BEGIN EC PRIVATE KEY-----
  여기에 키 내용...
  -----END EC PRIVATE KEY-----
  ```
- `VAPID_PUBLIC_KEY`: VAPID 공개 키
- `VAPID_EMAIL`: VAPID 이메일 (예: mailto:your-email@example.com)

#### 기타 설정
- `WEATHER_LOCATION`: 날씨 위치 (예: 일산)
- `SERVER_IP`: 서버 IP (기본값: 127.0.0.1)

### RSS 피드 설정

RSS 피드는 `rss_feeds.txt` 파일에서 관리됩니다. 이 파일은 리포지토리에 포함되므로 별도의 GitHub Secret 설정이 필요하지 않습니다.

`rss_feeds.txt` 파일 형식:
```
# 국내 기사 RSS 주소
조선일보-정치="https://www.chosun.com/arc/outboundfeeds/rss/category/politics/?outputType=xml"
연합뉴스-정치="https://www.yna.co.kr/rss/politics.xml"

# 해외 기사 RSS 주소
BBC_WORLD="https://feeds.bbci.co.uk/news/world/rss.xml"
```

**참고**: 민감하지 않은 공개 RSS 주소이므로 리포지토리에 안전하게 커밋할 수 있습니다.

## 3. 실행 스케줄 (현재: systemd 타이머)

**현재 시스템은 systemd 타이머를 사용하여 매일 오전 6시에 자동 실행됩니다.**

### systemd 타이머 설정
- **메인 뉴스**: 매일 오전 6:00 KST (`morningnews.timer` → `morningnews.service`)
- **YouTube 뉴스**: 매일 오전 6:10 KST (`morningnews-youtube.timer` → `morningnews-youtube.service`)

### 실행 흐름
1. systemd 타이머가 `run_morningnews.sh` 스크립트 실행
2. `git pull --ff-only`로 최신 코드 동기화
3. `python3 main.py`로 뉴스 생성
4. 변경사항을 자동으로 `git commit` → `git push`
5. GitHub Pages를 통해 PWA 앱에서 확인

### 타이머 상태 확인
```bash
# 타이머 상태 확인
systemctl status morningnews.timer

# 실행 로그 확인
cat /data/projects/morningnews/logs/morningnews_$(date +'%Y%m%d').log
```

## 4. GitHub Actions (백업/수동 실행용)

GitHub Actions는 `workflow_dispatch`로 설정되어 있어 수동 실행만 가능합니다.

- **수동 실행**: GitHub Actions 탭에서 "Run workflow" 버튼 클릭
- **용도**: 서버 접근 불가 시 백업용 또는 테스트용 실행

### GitHub Actions에 cron 스케줄 추가 방법 (선택사항)

`.github/workflows/morning-news.yml` 파일에 schedule을 추가하면 자동 실행도 설정할 수 있습니다:

```yaml
on:
  workflow_dispatch:  # 수동 실행
  schedule:
    - cron: '30 23 * * *'  # 매일 UTC 23:30 (KST 08:30)
```

### Cron 표현식 예시
- `30 23 * * *` - 매일 UTC 23:30 (KST 08:30)
- `0 0 * * *` - 매일 UTC 00:00 (KST 09:00)
- `0 22 * * *` - 매일 UTC 22:00 (KST 07:00)

**참고**: GitHub Actions는 UTC 시간대를 사용하므로 한국 시간(KST)에서 9시간을 빼야 합니다.

## 5. 출력 파일 확인

생성된 뉴스 파일은 다음 방법으로 확인할 수 있습니다:

1. **PWA 앱**: GitHub Pages URL에서 직접 확인
2. **Repository 파일**: `output/` 폴더에 날짜별 HTML 파일이 저장됩니다
3. **GitHub Actions Artifacts** (수동 실행 시):
   - Actions 탭 > 해당 workflow 클릭 > Artifacts 섹션에서 `morning-news-output` 다운로드

## 6. 로그 확인

- **systemd 실행 로그**: `/data/projects/morningnews/logs/morningnews_YYYYMMDD.log`
- **GitHub Actions 로그**: Actions 탭에서 각 실행 결과의 상세 로그 확인

## 7. 문제 해결

### Workflow가 실행되지 않는 경우
1. Repository Settings > Actions > General에서 workflow 권한이 활성화되어 있는지 확인
2. Secrets가 올바르게 설정되어 있는지 확인

### API 키 오류
- Secrets에 설정된 값들이 올바른지 확인
- VAPID_PRIVATE_KEY는 전체 PEM 형식이 포함되어야 함

### Git Push 권한 오류
- Repository Settings > Actions > General > Workflow permissions에서 "Read and write permissions" 선택

## 8. 비용

GitHub Actions는 퍼블릭 저장소의 경우 무료입니다.
프라이빗 저장소의 경우 월 2,000분까지 무료이며, 이 봇은 실행당 약 2-5분 소요됩니다.

## 9. 주의사항

- `.env` 파일과 `vapid_private.pem` 파일을 Git에 커밋하지 마세요 (`.gitignore`에 추가됨)
- `rss_feeds.txt` 파일은 리포지토리에 포함해야 합니다 (공개 RSS 주소이므로 안전)
- 모든 민감한 정보는 GitHub Secrets를 통해 관리하세요
- API 키와 토큰은 주기적으로 갱신하는 것을 권장합니다
