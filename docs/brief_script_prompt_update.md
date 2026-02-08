# v4.1 브리프 스크립트 프롬프트 적용 내역

## 목적
OpenAI 호출 1회로 **source_script(SRT용)** 과 **read_script(TTS용)** 을 동시에 생성하고,
두 스크립트를 **단일 JSON 파일**로 저장하도록 파이프라인을 업데이트했습니다.

## 주요 변경 사항

### 1) 프롬프트 교체 (v4.1)
- 대상 파일: `sentiment_analyzer.py`
- 변경 내용:
  - OpenAI용 프롬프트를 v4.1 문서로 교체
  - `source_script` + `read_script` **동시 생성** 지시
  - 출력은 JSON만 허용하도록 유지 (system 메시지 + `json_object` 포맷)

### 2) 결과 저장 포맷
- 단일 파일 저장: `scripts/brief_YYYYMMDD.json`
- 저장 함수: `SentimentAnalyzer.save_brief_scripts_json(...)`
- 저장 내용:
  ```json
  {
    "source_script": { ... },
    "read_script": { ... }
  }
  ```

### 3) 파이프라인 연결
- 대상 파일: `main.py`
- 변경 내용:
  - 기존 TTS 텍스트 저장과 별도로 `brief_YYYYMMDD.json` 저장 추가

## 참고
- `read_script`에는 `[SMILE]`, `[PAUSE]` 같은 태그를 넣지 않습니다.
- 태그는 **별도 TTS 렌더링 단계**에서 추가하는 방향으로 유지합니다.
- Gemini 요약/선별 단계는 그대로 유지하며, OpenAI는 스크립트 생성에만 1회 호출됩니다.
