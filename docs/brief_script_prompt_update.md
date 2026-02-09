# v5.0 모닝뉴스 앵커 원고(source_script 단일) 개선 내역

## 목적
OpenAI 호출 1회로 **source_script(연속 원고 텍스트)** 만 생성하고,
해당 원고를 **flatten(TTS) 단계에서 문장 단위로 분해**하도록 파이프라인을 업데이트했습니다.

## 주요 변경 사항

### 1) 프롬프트 교체 (앵커 원고 규칙)
- 대상 파일: `sentiment_analyzer.py`
- 변경 내용:
  - “한국어 라디오 모닝뉴스 앵커” 규칙을 반영한 프롬프트로 교체
  - `source_script`는 **하나의 연속된 원고 텍스트**만 생성
  - 섹션 제목/불릿/목록형 문장 금지, 낭독체 톤 유지
  - 출력은 JSON만 허용하도록 유지 (`json_object` 포맷)

### 2) 결과 저장 포맷
- 단일 파일 저장: `scripts/brief_YYYYMMDD.json`
- 저장 함수: `SentimentAnalyzer.save_brief_scripts_json(...)`
- 저장 내용:
  ```json
  {
    "source_script": "...연속 원고 텍스트..."
  }
  ```

### 3) 파이프라인 연결
- 대상 파일: `main.py`
- 변경 내용:
  - 기존 TTS 텍스트 저장과 별도로 `brief_YYYYMMDD.json` 저장 추가
  - `source_script`가 문자열일 때만 저장하도록 조건 처리

### 4) flatten(TTS) 로직 보정
- 대상 파일: `sentiment_analyzer.py`
- 변경 내용:
  - `_build_tts_lines_from_source_script()`가 **문자열 source_script**를 처리하도록 확장
  - 문단/문장 단위 split 후 길이가 긴 문장은 쉼표/접속어 기준으로 추가 분할
  - ‘또’ 분리 규칙 제거로 클로징 문장 리듬 유지
  - 기존 dict 구조 source_script도 하위 호환 유지

## 테스트 메모
- .venv 환경에서 샘플 원고를 넣어 문장 단위 분할이 자연스럽게 동작하는지 확인

## 참고
- Gemini 요약/선별 단계는 그대로 유지하며, OpenAI는 스크립트 생성에만 1회 호출됩니다.
- TTS 스크립트의 인트로/아웃트로 고정 규칙은 기존대로 유지됩니다.
