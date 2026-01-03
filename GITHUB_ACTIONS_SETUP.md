# GitHub Actions 설정 가이드

이 문서는 모닝뉴스봇을 GitHub Actions로 자동화하기 위한 설정 가이드입니다.

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

## 3. 실행 스케줄

GitHub Actions workflow는 다음과 같이 실행됩니다:

- **자동 실행**: 매일 오전 8시 30분 (KST) - UTC 23:30
- **수동 실행**: GitHub Actions 탭에서 "Run workflow" 버튼 클릭

## 4. 스케줄 시간 변경

`.github/workflows/morning-news.yml` 파일에서 cron 표현식을 수정하세요:

```yaml
schedule:
  - cron: '30 23 * * *'  # UTC 시간 기준
```

### Cron 표현식 예시
- `30 23 * * *` - 매일 UTC 23:30 (KST 08:30)
- `0 0 * * *` - 매일 UTC 00:00 (KST 09:00)
- `0 22 * * *` - 매일 UTC 22:00 (KST 07:00)

**참고**: GitHub Actions는 UTC 시간대를 사용하므로 한국 시간(KST)에서 9시간을 빼야 합니다.

## 5. 출력 파일 확인

생성된 뉴스 파일은 다음 방법으로 확인할 수 있습니다:

1. **GitHub Actions Artifacts**: 
   - Actions 탭 > 해당 workflow 클릭 > Artifacts 섹션에서 `morning-news-output` 다운로드

2. **Repository 파일**:
   - `output/` 폴더에 자동으로 커밋되어 저장됩니다

## 6. 로그 확인

- GitHub Actions 탭에서 각 실행 결과의 상세 로그를 확인할 수 있습니다
- `run_job.log` 파일도 Artifacts에 포함됩니다

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
