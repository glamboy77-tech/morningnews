# 모닝뉴스 뉴스 소스 확장 업데이트 정리

작성일: 2026-07-10  
대상 프로젝트: `morningnews`

---

## 1. 업데이트 목적

이번 업데이트의 목적은 기존 모닝뉴스가 가진 가장 큰 한계였던 **뉴스 소스의 제한성**을 개선하는 것입니다.

기존 구조는 안정적이었지만, 대부분 RSS 피드 기반의 일부 언론사 기사에 의존했습니다. 따라서 다음과 같은 아쉬움이 있었습니다.

- 같은 매체/같은 성격의 기사 비중이 높음
- 정책 원문, 공식기관 발표, 공시 같은 1차 정보가 부족함
- 부동산, 산업, AI/테크, 거시경제 등 관심 영역을 더 촘촘히 잡기 어려움
- 특정 키워드 이슈가 RSS 피드에 없으면 누락될 수 있음

이번 업데이트는 이를 해결하기 위해 아래 방향으로 설계했습니다.

```text
언론 RSS 확대
+ 경제/산업/테크/부동산 전문 소스 추가
+ 공식기관 보도자료 보강
+ 관심 키워드 기반 Google News RSS 추가
+ 선택적 DART 공시 수집
+ 중복제거
+ 소스별 가중치 부여
+ HTML에서 소스 성격 표시
```

---

## 2. 전체 구조 변화 요약

### 기존 구조

```text
RSSManager
  → 언론 RSS 수집
  → main.py
  → AI 분류
  → 브리핑 생성
  → HTML 생성
```

### 업데이트 후 구조

```text
RSSManager
  → 일반 언론 RSS
  → 경제/산업 RSS
  → IT/테크 RSS
  → 부동산 RSS
  → 공식기관 Google News RSS
  → 관심 키워드 Google News RSS
  → 소스 타입/가중치 부여
  → 중복제거

DARTManager 선택 실행
  → OPEN_DART_API_KEY 또는 DART_API_KEY가 있을 때만 실행
  → 중요 공시 수집
  → 기존 뉴스 아이템 포맷으로 변환

main.py
  → RSS + DART 병합
  → 최종 중복제거
  → 기존 AI 분류 파이프라인으로 전달
```

핵심은 **수집 레이어는 확장하되, AI 분류/브리핑/HTML 생성 파이프라인은 최대한 유지**한 것입니다.

---

## 3. 변경된 주요 파일

### 수정된 파일

```text
rss_feeds.txt
rss_manager.py
main.py
ai_processor.py
html_generator.py
config.py
```

### 새로 추가된 파일

```text
dart_manager.py
```

---

## 4. RSS 소스 확장

파일:

```text
/data/projects/morningnews/rss_feeds.txt
```

기존 RSS 피드에 더해 여러 소스가 추가되었습니다.

### 4-1. 경제/산업 보강

추가된 대표 소스:

```text
연합뉴스-경제
연합뉴스-산업
매일경제-경제
매일경제-기업
한국경제-경제
서울경제-경제
이데일리-경제
머니투데이-경제
조선비즈
```

목적:

- 거시경제 흐름 강화
- 기업/산업 뉴스 보강
- 증시, 환율, 금리, 수출, 산업 정책 관련 뉴스 확대

---

### 4-2. IT/테크/과학 보강

추가된 대표 소스:

```text
전자신문
ZDNetKorea
디지털데일리
AI타임스
블로터
```

목적:

- AI
- 반도체
- 플랫폼
- 로봇
- 클라우드
- 소프트웨어
- 스타트업

관련 흐름을 더 잘 포착하기 위함입니다.

---

### 4-3. 부동산/건설 보강

추가된 대표 소스:

```text
한국경제-부동산
이데일리-부동산
대한경제
```

목적:

- 재건축/재개발
- 분양가
- 전세
- GTX
- 건설사
- 주택정책
- 지역 개발

관련 뉴스 보강입니다.

---

### 4-4. 공식기관 보도자료 보강

공식기관 자료는 직접 RSS가 안정적으로 제공되지 않는 경우가 많기 때문에, 이번 업데이트에서는 **Google News RSS 검색 피드**를 활용했습니다.

추가된 공식기관 계열:

```text
공식-한국은행
공식-금융위원회
공식-금융감독원
공식-기획재정부
공식-국토교통부
공식-산업통상자원부
공식-통계청
공식-공정거래위원회
공식-서울시
```

예시:

```text
공식-한국은행="https://news.google.com/rss/search?q=site:bok.or.kr+보도자료+when:2d&hl=ko&gl=KR&ceid=KR:ko"
```

목적:

- 언론 보도 이전의 원문성 정보 확보
- 정책 발표의 정확성 보강
- 금리, 물가, 주택정책, 금융규제, 산업정책 등 핵심 주제 보강

---

### 4-5. 관심 키워드 RSS 추가

특정 관심사를 놓치지 않기 위해 Google News RSS 기반 키워드 피드를 추가했습니다.

추가된 키워드 피드:

```text
키워드-금리환율코스피
키워드-반도체AI
키워드-부동산정책
키워드-용산일산
키워드-에너지물가
```

목적:

- 기본 RSS에 없는 관심 이슈 보강
- 특정 키워드 중심의 개인화 감각 강화
- 용산, 일산, GTX, 재건축, 반도체, AI, 환율 등 주요 관심사 추적

---

## 5. RSSManager 개선

파일:

```text
/data/projects/morningnews/rss_manager.py
```

이번 업데이트에서 `RSSManager`는 단순 RSS 수집기에서 **뉴스 소스 정규화/품질 관리 레이어** 역할까지 하게 되었습니다.

---

### 5-1. 소스 타입 분류

새로 추가된 함수:

```python
infer_source_type(source_name, url)
```

소스 이름과 URL을 보고 소스 성격을 판정합니다.

대표 타입:

```text
official        공식기관
disclosure      공시
wire            통신사
economy         경제지/경제 소스
tech            테크/과학 소스
realestate      부동산/건설 소스
google_keyword  Google News 관심 키워드
rss             일반 언론 RSS
```

---

### 5-2. 소스 가중치 부여

각 소스 타입에는 기본 가중치가 붙습니다.

```python
SOURCE_TYPE_META = {
    "official": {"weight": 1.6, "badge": "공식"},
    "disclosure": {"weight": 1.6, "badge": "공시"},
    "wire": {"weight": 1.25, "badge": "통신"},
    "economy": {"weight": 1.2, "badge": "경제"},
    "tech": {"weight": 1.15, "badge": "테크"},
    "realestate": {"weight": 1.15, "badge": "부동산"},
    "google_keyword": {"weight": 0.85, "badge": "키워드"},
    "rss": {"weight": 1.0, "badge": "언론"},
}
```

이 메타데이터는 각 뉴스 아이템에 다음 필드로 들어갑니다.

```python
source_type
source_weight
source_badge
```

예시:

```python
{
    "source": "공식-한국은행",
    "source_type": "official",
    "source_weight": 1.6,
    "source_badge": "공식"
}
```

---

### 5-3. 중복제거 추가

새 함수:

```python
deduplicate_news_items(items)
```

중복 판단 기준:

- 정규화한 URL
- 정규화한 제목

중복이 발견되면 더 높은 `source_weight`를 가진 기사를 대표로 남기고, 다른 기사는 `deduped_sources`에 보관합니다.

예시:

```python
deduped_sources = [
    {
        "source": "다른매체",
        "title": "같은 이슈 기사 제목",
        "link": "..."
    }
]
```

실제 테스트에서는 다음처럼 확인되었습니다.

```text
Dedupe removed/merged 109 duplicate RSS items
```

---

### 5-4. 피드별 수집 상한

소스가 대폭 늘어나면서 기사 수가 과도하게 증가할 수 있으므로, 피드별 수집 상한을 추가했습니다.

```text
Google News 키워드 RSS: 최대 25개
공식기관 RSS: 최대 40개
통신/경제 RSS: 최대 80개
기타 RSS: 최대 60개
```

목적:

- LLM 분류 비용 급증 방지
- Google News 키워드 피드의 노이즈 억제
- 피드 하나가 전체 수집량을 과도하게 차지하는 문제 방지

---

## 6. DART 공시 수집 추가

새 파일:

```text
/data/projects/morningnews/dart_manager.py
```

이번 업데이트에서 `DARTManager`가 새로 추가되었습니다.

---

### 6-1. 동작 조건

DART 수집은 기본적으로 꺼져 있습니다. 아래 환경변수 중 하나가 있을 때만 활성화됩니다.

```env
OPEN_DART_API_KEY=발급받은_오픈다트_API_KEY
```

또는:

```env
DART_API_KEY=발급받은_오픈다트_API_KEY
```

키가 없으면 다음 메시지를 출력하고 건너뜁니다.

```text
OpenDART API 키가 없어 DART 공시 수집을 건너뜁니다.
```

---

### 6-2. 수집 대상

모든 공시를 가져오면 노이즈가 너무 많으므로, 중요해 보이는 공시만 필터링합니다.

중요 공시 키워드 예시:

```text
주요사항보고서
단일판매
공급계약
신규시설투자
자기주식
유상증자
무상증자
전환사채
신주인수권
최대주주
영업정지
회생절차
소송
잠정실적
영업실적
배당
합병
분할
상장폐지
```

---

### 6-3. 기존 뉴스 포맷으로 변환

DART 공시는 기존 RSS 기사와 같은 구조로 변환됩니다.

예시:

```python
{
    "title": "[DART] 삼성전자: 신규시설투자",
    "link": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=...",
    "source": "DART",
    "published_dt": datetime(...),
    "description": "삼성전자 공시 - 신규시설투자 / 접수일 ...",
    "category": "domestic",
    "source_type": "disclosure",
    "source_badge": "공시",
    "source_weight": 1.6
}
```

이렇게 변환하기 때문에 기존 AI 분류 파이프라인을 거의 수정하지 않고도 공시를 함께 분석할 수 있습니다.

---

## 7. main.py 연결 방식

파일:

```text
/data/projects/morningnews/main.py
```

새 헬퍼 함수가 추가되었습니다.

```python
fetch_fresh_news(rss, dart, use_dart=True)
```

역할:

```text
1. RSSManager로 RSS 전체 수집
2. DARTManager로 중요 공시 수집
3. DART 결과가 있으면 RSS와 병합
4. 최종 중복제거
5. 기존 all_news로 반환
```

실행 흐름은 다음과 같습니다.

```text
캐시 있음
  → data_cache/rss_YYYYMMDD.json 로드

캐시 없음 또는 로드 실패
  → RSS 전체 수집
  → DART API 키가 있으면 공시 수집
  → RSS + DART 병합
  → 중복제거
  → data_cache/rss_YYYYMMDD.json 저장
```

---

## 8. AI 분류 우선순위 개선

파일:

```text
/data/projects/morningnews/ai_processor.py
```

기존에는 `config.target_keywords`에 포함된 키워드가 제목/설명에 있으면 점수를 주는 방식이었습니다.

이번 업데이트 후에는 다음 요소도 점수에 반영됩니다.

```text
관심 키워드 점수
+ 소스 가중치 점수
+ 공식기관/공시 가산점
+ 중복 보도량 가산점
```

로직 개념:

```python
source_weight = item.get("source_weight", 1.0)
score = int(round((source_weight - 1.0) * 10))

if target_keyword in title_or_description:
    score += 5

if source_type in ("official", "disclosure"):
    score += 4

if deduped_sources:
    score += min(len(deduped_sources), 5)
```

즉, 공식기관 자료와 DART 공시는 더 높은 우선순위를 받을 수 있습니다.

---

## 9. HTML 표시 개선

파일:

```text
/data/projects/morningnews/html_generator.py
```

기사 카드의 메타 영역에 소스 성격이 표시됩니다.

예시:

```text
연합뉴스-경제 · 통신
공식-한국은행 · 공식
DART · 공시
전자신문 · 테크
키워드-반도체AI · 키워드
```

이 표시의 목적은 다음과 같습니다.

- 사용자가 기사 성격을 빠르게 파악
- 언론 기사와 공식자료를 구분
- Google News 키워드 보강 자료임을 구분
- DART 공시를 별도로 인지

---

## 10. 검증 결과

### 10-1. Python 문법 검사

아래 명령으로 문법 검사를 통과했습니다.

```bash
.venv/bin/python -m py_compile main.py rss_manager.py dart_manager.py ai_processor.py html_generator.py config.py
```

---

### 10-2. diff 공백 검사

아래 명령도 통과했습니다.

```bash
git diff --check
```

---

### 10-3. RSS 실제 수집 테스트

수집 테스트 결과:

```text
feeds 40
Dedupe removed/merged 109 duplicate RSS items
fetched_total 977
```

즉, 현재 설정 기준으로 40개 피드에서 수집을 시도했고, 중복 제거 후 약 977건의 뉴스 아이템이 확보되었습니다.

샘플 소스 타입도 정상적으로 붙었습니다.

```text
AI타임스 → tech / 테크
동아일보-국제 → rss / 언론
머니투데이-경제 → economy / 경제
```

---

### 10-4. DART 상태 확인

현재 환경에서는 DART API 키가 없어 비활성 상태였습니다.

```text
dart_enabled False
```

API 키를 추가하면 다음 실행부터 자동으로 DART 공시 수집이 활성화됩니다.

---

## 11. 운영 시 주의사항

### 11-1. 첫 실행 시 기사 수가 크게 늘어남

이번 테스트에서는 중복제거 후에도 약 977건이 수집되었습니다.

현재 AI 분류는 200개 단위 배치로 처리되므로, 대략 다음 정도의 분류 호출이 발생할 수 있습니다.

```text
977건 / 200개 ≒ 5개 배치
```

따라서 LLM 호출 시간과 비용이 기존보다 늘어날 수 있습니다.

---

### 11-2. 일부 RSS는 0건일 수 있음

테스트에서 일부 RSS는 0건으로 확인되었습니다.

예:

```text
한국경제-기업
한국경제-IT
매일경제-기업
서울경제-경제
이데일리-경제
디지털데일리
블로터
한국경제-부동산
이데일리-부동산
대한경제
```

가능한 원인:

- RSS URL이 더 이상 유효하지 않음
- 사이트가 RSS를 제공하지 않음
- feedparser가 파싱 가능한 표준 RSS가 아님
- 일시적인 네트워크/서버 응답 문제

현재 구조에서는 해당 피드가 실패하거나 0건이어도 전체 실행은 계속됩니다.

---

### 11-3. Google News RSS는 보조 소스로 사용해야 함

Google News RSS는 관심 키워드 보강에 유용하지만, 다음 단점이 있습니다.

- 중복이 많을 수 있음
- 원문 링크가 Google News 래핑 링크일 수 있음
- 특정 키워드에서 노이즈가 생길 수 있음
- 너무 많이 추가하면 AI 분류량이 증가함

그래서 이번 업데이트에서는 `google_keyword` 타입에 낮은 가중치인 `0.85`를 부여했습니다.

---

## 12. DART API 키 설정 방법

서버의 `.env`에 아래 중 하나를 추가합니다.

```env
OPEN_DART_API_KEY=발급받은_오픈다트_API_KEY
```

또는:

```env
DART_API_KEY=발급받은_오픈다트_API_KEY
```

적용 후 다음 실행부터 자동으로 DART 수집이 활성화됩니다.

확인 로그 예시:

```text
DART important disclosures: 12
DART 공시 병합: 12건
```

---

## 13. 향후 개선 추천

이번 업데이트는 1차 대규모 확장입니다. 다음 단계로는 아래를 추천합니다.

---

### 13-1. 0건 RSS 정리

현재 일부 피드는 0건입니다. 다음 작업에서 실제 동작하는 RSS 주소를 찾아 교체하거나 제거하면 좋습니다.

우선순위:

```text
한국경제 계열 RSS 교체
서울경제 RSS 확인
이데일리 RSS 확인
디지털데일리 RSS 확인
블로터 RSS 확인
대한경제 RSS 확인
```

---

### 13-2. AI 분류 전 Top N 선별 단계 추가

수집량이 900~1000건 수준으로 늘면 LLM 호출 비용이 증가할 수 있습니다.

따라서 AI 분류 전에 아래 기준으로 상위 N개를 선별하는 단계를 추가할 수 있습니다.

```text
최신성
source_weight
target_keywords
공식기관/공시 여부
중복 보도량
```

예:

```text
수집 1000건
→ 사전 랭킹 상위 500건
→ AI 분류
```

---

### 13-3. 오늘의 Top Themes 섹션 추가

소스가 늘어나면 단순 카테고리별 나열보다, 상단에 핵심 테마를 보여주는 것이 더 좋습니다.

예:

```text
오늘의 핵심 테마 5개
1. 환율 급등과 수입물가 부담
2. 반도체 AI 투자 경쟁
3. 부동산 전세 불안과 정책 대응
4. DART 주요 공시: 대규모 공급계약
5. 국제유가와 생활물가 영향
```

이 기능은 별도 LLM 요약 단계로 만들 수 있습니다.

---

### 13-4. 소스별 수집량 리포트 저장

매일 어떤 소스에서 몇 건이 들어왔는지 저장하면 RSS 튜닝이 쉬워집니다.

예:

```json
{
  "연합뉴스-경제": 80,
  "공식-한국은행": 5,
  "키워드-반도체AI": 25,
  "DART": 12
}
```

저장 위치 예시:

```text
data_cache/source_stats_YYYYMMDD.json
```

---

### 13-5. 공식기관 직접 RSS/API 전환

현재 공식기관은 Google News RSS 기반입니다. 더 안정적인 운영을 위해 장기적으로는 직접 RSS/API 또는 보도자료 페이지 파서를 붙이는 것도 가능합니다.

대상 후보:

```text
한국은행
금융위원회
금융감독원
국토교통부
기획재정부
통계청
공정거래위원회
```

다만 직접 크롤링은 유지보수 부담이 있으므로, 현재는 Google News RSS 보강 방식이 더 안전합니다.

---

## 14. 이번 업데이트의 기대 효과

이번 업데이트로 기대되는 변화는 다음과 같습니다.

```text
뉴스 소스 다양성 증가
정책/공식자료 보강
기업 공시 기반 정보 추가 가능
관심 키워드 누락 감소
소스별 신뢰도/성격 구분 가능
중복 기사 일부 자동 병합
AI 분류 우선순위 개선
HTML에서 공식/공시/키워드 구분 가능
```

결과적으로 모닝뉴스가 단순 RSS 모음에서 한 단계 더 나아가, **언론 보도 + 공식자료 + 공시 + 관심 키워드를 통합하는 아침 브리핑 시스템**에 가까워졌습니다.

---

## 15. 한 줄 요약

이번 업데이트는 모닝뉴스의 수집층을 `언론 RSS 중심`에서 `언론 RSS + 공식기관 + 관심 키워드 + 선택적 DART 공시` 구조로 확장하고, 각 기사에 소스 가중치와 소스 뱃지를 부여해 더 풍부하고 신뢰도 있는 아침 뉴스 생성을 가능하게 한 업데이트입니다.
