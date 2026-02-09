from google import genai
from openai import OpenAI
import json
import re
import os
import time
import glob
import random
from datetime import datetime, timedelta, timezone
from config import config

class SentimentAnalyzer:
    def __init__(self):
        self.client = genai.Client(api_key=config.gemini_api_key)
        self.openai_client = OpenAI(api_key=config.openai_api_key) if config.openai_api_key else None
        self.cache_dir = "sentiment_cache"
        os.makedirs(self.cache_dir, exist_ok=True)
        self.tts_dir = "scripts"
        os.makedirs(self.tts_dir, exist_ok=True)
        self.brief_dir = "scripts"
        os.makedirs(self.brief_dir, exist_ok=True)

    @staticmethod
    def _kst_now():
        return datetime.now(timezone(timedelta(hours=9)))

    @staticmethod
    def _format_korean_date(date_obj: datetime) -> str:
        return f"{date_obj.month}월 {date_obj.day}일"

    # -----------------------------
    # Cache helpers
    # -----------------------------
        
    def is_trading_day(self):
        """
        현재가 평일 장 중인지, 아니면 주말/공휴일인지 판단
        Returns: 'trading' (평일 장 중) or 'accumulation' (주말/공휴일)
        """
        now = datetime.now()
        
        # 주말 체크
        if now.weekday() >= 5:  # 토요일(5), 일요일(6)
            return 'accumulation'
        
        # 공휴일 체크 (간단한 한국 공휴일 목록)
        month = now.month
        day = now.day
        
        korean_holidays = {
            (1, 1): "신정",
            (3, 1): "삼일절",
            (5, 5): "어린이날",
            (6, 6): "현충일",
            (8, 15): "광복절",
            (10, 3): "개천절",
            (10, 9): "한글날",
            (12, 25): "성탄절"
        }
        
        if (month, day) in korean_holidays:
            return 'accumulation'
        
        # 장 시간 체크 (평일 9:00-15:30)
        if 9 <= now.hour < 16:
            return 'trading'
        else:
            return 'accumulation'
    
    def is_first_trading_day_after_holiday(self):
        """
        월요일 또는 공휴일 다음 날인지 판단
        Returns: True if today is the first trading day after a holiday/weekend
        """
        now = datetime.now()
        
        # 월요일 체크
        if now.weekday() == 0:  # 0은 월요일
            return True
        
        # 어제가 공휴일이었는지 체크
        yesterday = now - timedelta(days=1)
        yesterday_month = yesterday.month
        yesterday_day = yesterday.day
        
        korean_holidays = {
            (1, 1): "신정",
            (3, 1): "삼일절",
            (5, 5): "어린이날",
            (6, 6): "현충일",
            (8, 15): "광복절",
            (10, 3): "개천절",
            (10, 9): "한글날",
            (12, 25): "성탄절"
        }
        
        # 어제가 주말이거나 공휴일이었으면 True
        if yesterday.weekday() >= 5 or (yesterday_month, yesterday_day) in korean_holidays:
            return True
        
        return False
    
    def get_time_weight(self, news_datetime):
        """
        뉴스 시간에 따른 가중치 계산
        - 어제 15:30 ~ 오늘 08:30: 가중치 2.0 (장외 뉴스)
        - 어제 09:00 ~ 15:30: 가중치 1.0 (장중 뉴스)
        - 그 외: 가중치 0.5 (기타)
        """
        now = datetime.now()
        yesterday = now - timedelta(days=1)
        
        # 장외 시간대: 어제 15:30 ~ 오늘 08:30
        market_close_yesterday = yesterday.replace(hour=15, minute=30, second=0, microsecond=0)
        market_open_today = now.replace(hour=8, minute=30, second=0, microsecond=0)
        
        # 장중 시간대: 어제 09:00 ~ 15:30
        market_open_yesterday = yesterday.replace(hour=9, minute=0, second=0, microsecond=0)
        
        if market_close_yesterday <= news_datetime <= market_open_today:
            return 2.0  # 장외 뉴스 (가장 중요)
        elif market_open_yesterday <= news_datetime < market_close_yesterday:
            return 1.0  # 장중 뉴스 (이미 반영됨)
        else:
            return 0.5  # 기타 뉴스
    
    def filter_trading_signals(self, categorized_news):
        """
        매매봇용 호재/악재 필터링
        - 장외 뉴스(어제 15:30~오늘 08:30)에 가중치 부여
        """
        filtered_news = {}
        
        for category, items in categorized_news.items():
            filtered_items = []
            
            for item in items:
                news_time = item.get('published_dt')
                if news_time:
                    weight = self.get_time_weight(news_time)
                    # 가중치가 1.0 이상인 뉴스만 포함 (장외 + 장중)
                    if weight >= 1.0:
                        item['time_weight'] = weight
                        filtered_items.append(item)
            
            if filtered_items:
                filtered_news[category] = filtered_items
        
        return filtered_news
    
    def get_cache_filename(self, date_str=None):
        """
        캐시 파일명 생성
        """
        if date_str is None:
            date_str = self._kst_now().strftime("%Y%m%d")
        return os.path.join(self.cache_dir, f"sentiment_{date_str}.json")

    def _find_latest_cache_file(self, exclude_date_str=None, max_age_days: int | None = 2):
        """Find newest sentiment_YYYYMMDD.json.

        Args:
            exclude_date_str: 특정 날짜(YYYYMMDD)는 제외
            max_age_days: 오늘 기준 최대 몇 일 전까지 허용할지. None이면 제한 없음.

        Returns:
            (date_str, path) or (None, None)
        """
        candidates = sorted(glob.glob(os.path.join(self.cache_dir, "sentiment_*.json")))
        # Sort by filename date then mtime as tie-breaker
        def _key(p):
            base = os.path.basename(p)
            m = base.replace("sentiment_", "").replace(".json", "")
            try:
                dt = datetime.strptime(m, "%Y%m%d")
            except Exception:
                dt = datetime.fromtimestamp(os.path.getmtime(p))
            return (dt, os.path.getmtime(p))
        candidates.sort(key=_key, reverse=True)

        now = datetime.now()
        for path in candidates:
            base = os.path.basename(path)
            date_str = base.replace("sentiment_", "").replace(".json", "")
            if exclude_date_str and date_str == exclude_date_str:
                continue

            if max_age_days is not None:
                try:
                    dt = datetime.strptime(date_str, "%Y%m%d")
                    if (now - dt).days > max_age_days:
                        continue
                except Exception:
                    # If we can't parse date, skip it when age limiting is enabled
                    continue

            return date_str, path
        return None, None
    
    def load_cached_data(self, date_str=None):
        """
        캐시된 데이터 로드
        """
        cache_file = self.get_cache_filename(date_str)
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"캐시 로드 실패: {e}")
        return None
    
    def save_cached_data(self, data, date_str=None):
        """
        데이터 캐시 저장
        """
        cache_file = self.get_cache_filename(date_str)
        tmp_file = f"{cache_file}.tmp"
        try:
            with open(tmp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_file, cache_file)
            print(f"✅ 감성 데이터 캐시 저장: {cache_file}")
        except Exception as e:
            if os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except Exception:
                    pass
            print(f"캐시 저장 실패: {e}")

    # -----------------------------
    # Retry helpers
    # -----------------------------
    @staticmethod
    def _is_retryable_error(err: Exception) -> bool:
        msg = str(err)
        # Gemini/Google GenAI commonly returns "503 UNAVAILABLE" when overloaded.
        return (
            "503" in msg
            or "UNAVAILABLE" in msg
            or "RESOURCE_EXHAUSTED" in msg
            or "429" in msg
            or "overloaded" in msg.lower()
            or "rate" in msg.lower() and "limit" in msg.lower()
        )

    def _generate_json_with_retry(self, prompt: str, *, model: str, max_retries: int = 3, base_sleep_sec: float = 3.0):
        last_err = None
        for attempt in range(1, max_retries + 1):
            try:
                resp = self.client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config={'response_mime_type': 'application/json'}
                )
                return json.loads(resp.text)
            except Exception as e:
                last_err = e
                if attempt < max_retries and self._is_retryable_error(e):
                    jitter = random.uniform(0.0, base_sleep_sec * 0.6)
                    sleep_sec = base_sleep_sec * (2 ** (attempt - 1)) + jitter
                    print(f"⚠️ Gemini 호출 실패(재시도 {attempt}/{max_retries}): {e}")
                    print(f"   -> {sleep_sec:.1f}s 후 재시도")
                    time.sleep(sleep_sec)
                    continue
                raise

        # Should never reach here
        raise last_err

    def _generate_text_with_openai(self, prompt: str, *, model: str, max_retries: int = 3, base_sleep_sec: float = 3.0) -> str:
        if not self.openai_client:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        last_err = None
        for attempt in range(1, max_retries + 1):
            try:
                resp = self.openai_client.responses.create(
                    model=model,
                    input=[
                        {
                            "role": "system",
                            "content": "You output plain text only. Do not include JSON, markdown, or commentary.",
                        },
                        {
                            "role": "user",
                            "content": prompt,
                        },
                    ],
                )
                payload = resp.output_text or ""
                return payload.strip()
            except Exception as e:
                last_err = e
                if attempt < max_retries and self._is_retryable_error(e):
                    jitter = random.uniform(0.0, base_sleep_sec * 0.6)
                    sleep_sec = base_sleep_sec * (2 ** (attempt - 1)) + jitter
                    print(f"⚠️ OpenAI 호출 실패(재시도 {attempt}/{max_retries}): {e}")
                    print(f"   -> {sleep_sec:.1f}s 후 재시도")
                    time.sleep(sleep_sec)
                    continue
                raise

        raise last_err

    def _generate_tts_script_with_openai(self, prompt: str, *, model: str, max_retries: int = 3, base_sleep_sec: float = 3.0) -> dict:
        """Generate anchor script using OpenAI chat.completions API and return JSON.

        Args:
            prompt: The prompt to send to OpenAI
            model: The model to use (e.g., "gpt-4o")
            max_retries: Maximum number of retry attempts
            base_sleep_sec: Base sleep duration for exponential backoff

        Returns:
            dict: Parsed JSON response containing source_script only
        """
        if not self.openai_client:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        last_err = None
        for attempt in range(1, max_retries + 1):
            try:
                resp = self.openai_client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a Korean news briefing script writer. Output ONLY valid JSON, no markdown, no commentary, no code blocks.",
                        },
                        {
                            "role": "user",
                            "content": prompt,
                        },
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.7,
                )
                
                content = resp.choices[0].message.content
                if not content:
                    raise ValueError("OpenAI returned empty content")
                
                # Parse JSON response
                try:
                    result = json.loads(content)
                    # Expect source_script to be plain text (string)
                    source_script = result.get("source_script") if isinstance(result, dict) else None
                    if not isinstance(source_script, str) or not source_script.strip():
                        raise ValueError("OpenAI response missing valid source_script text")
                    return result
                except json.JSONDecodeError as je:
                    print(f"⚠️ JSON 파싱 실패: {je}")
                    print(f"   응답 내용: {content[:200]}...")
                    raise ValueError(f"Invalid JSON response from OpenAI: {je}")
                    
            except Exception as e:
                last_err = e
                if attempt < max_retries and self._is_retryable_error(e):
                    jitter = random.uniform(0.0, base_sleep_sec * 0.6)
                    sleep_sec = base_sleep_sec * (2 ** (attempt - 1)) + jitter
                    print(f"⚠️ OpenAI 호출 실패(재시도 {attempt}/{max_retries}): {e}")
                    print(f"   -> {sleep_sec:.1f}s 후 재시도")
                    time.sleep(sleep_sec)
                    continue
                raise

        raise last_err
    
    def merge_sentiment_data(self, current_data, cached_data):
        """
        현재 데이터와 캐시된 데이터를 병합
        - 동일 종목은 점수 합산
        - 새로운 종목은 추가
        """
        if not cached_data:
            return current_data
        
        merged = {
            "section_summaries": cached_data.get("section_summaries", {}),
            "hojae": [],
            "akjae": [],
            "merged_dates": cached_data.get("merged_dates", [])
        }
        
        # 현재 날짜 추가
        today = datetime.now().strftime("%Y-%m-%d")
        if today not in merged["merged_dates"]:
            merged["merged_dates"].append(today)
        
        # 호재 데이터 병합
        hojae_dict = {}
        
        # 캐시된 호재 데이터 처리
        for item in cached_data.get("hojae", []):
            if ":" in item:
                company, reason = item.split(":", 1)
                hojae_dict[company.strip()] = {
                    "reason": reason.strip(),
                    "count": 1,
                    "score": 1
                }
        
        # 현재 호재 데이터 처리 및 병합
        for item in current_data.get("hojae", []):
            if ":" in item:
                company, reason = item.split(":", 1)
                company = company.strip()
                if company in hojae_dict:
                    hojae_dict[company]["count"] += 1
                    hojae_dict[company]["score"] += 1
                    # 최신 이유로 업데이트
                    hojae_dict[company]["reason"] = reason.strip()
                else:
                    hojae_dict[company] = {
                        "reason": reason.strip(),
                        "count": 1,
                        "score": 1
                    }
        
        # 병합된 호재 데이터 생성
        for company, data in hojae_dict.items():
            merged["hojae"].append(f"{company}: {data['reason']} ({data['count']}회)")
        
        # 악재 데이터 병합 (동일 로직)
        akjae_dict = {}
        
        for item in cached_data.get("akjae", []):
            if ":" in item:
                company, reason = item.split(":", 1)
                akjae_dict[company.strip()] = {
                    "reason": reason.strip(),
                    "count": 1,
                    "score": -1
                }
        
        for item in current_data.get("akjae", []):
            if ":" in item:
                company, reason = item.split(":", 1)
                company = company.strip()
                if company in akjae_dict:
                    akjae_dict[company]["count"] += 1
                    akjae_dict[company]["score"] -= 1
                    akjae_dict[company]["reason"] = reason.strip()
                else:
                    akjae_dict[company] = {
                        "reason": reason.strip(),
                        "count": 1,
                        "score": -1
                    }
        
        for company, data in akjae_dict.items():
            merged["akjae"].append(f"{company}: {data['reason']} ({data['count']}회)")
        
        return merged
    
    def _fallback_briefing(self, *, error: str, source_date: str | None = None):
        base_sections = {"정치": "", "경제/거시": "", "기업/산업": "", "부동산": "", "국제": ""}
        msg = "브리핑 생성에 실패했습니다. 잠시 후 다시 시도해주세요."
        if source_date:
            msg = f"오늘 브리핑 생성에 실패하여 최근 캐시({source_date})를 표시합니다."
        base_sections["경제/거시"] = msg
        return {
            "section_summaries": base_sections,
            "hojae": [],
            "akjae": [],
            "analysis_mode": None,
            "is_holiday_next_day": False,
            "meta": {
                "generated_by": "fallback",
                "error": error,
                "source_date": source_date,
                "generated_at": datetime.now().isoformat(),
            },
        }

    def _ensure_tts_script(self, data: dict, date_str: str | None = None) -> dict:
        """Ensure tts_script exists and is well-formed for backward compatibility."""
        if data is None:
            return data
        if not isinstance(data, dict):
            print(f"⚠️ _ensure_tts_script received non-dict: {type(data)}")
            return {
                "section_summaries": {"정치": "", "경제/거시": "", "기업/산업": "", "부동산": "", "국제": ""},
                "hojae": [],
                "akjae": [],
                "tts_script": {},
                "meta": {
                    "generated_by": "fallback",
                    "error": f"non-dict briefing data: {type(data)}",
                    "generated_at": datetime.now().isoformat(),
                },
            }

        if date_str is None:
            date_str = self._kst_now().strftime("%Y%m%d")
        date_str_dash = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

        tts_script = data.get("tts_script")
        if not isinstance(tts_script, dict):
            tts_script = {}

        tts_script.setdefault("duration_sec_target", 300)
        tts_script.setdefault("title", f"오늘의 모닝뉴스 ({date_str_dash})")

        pronunciations = tts_script.get("pronunciations", [])
        if not isinstance(pronunciations, list):
            pronunciations = []
        tts_script["pronunciations"] = pronunciations

        lines = tts_script.get("lines", [])
        if isinstance(lines, str):
            lines = [lines]
        if not isinstance(lines, list):
            lines = []
        tts_script["lines"] = [str(line).strip() for line in lines if str(line).strip()]

        data["tts_script"] = tts_script
        return data

    def _build_tts_fallback_content(self, briefing_data: dict, date_str: str | None = None) -> list[str]:
        """Build a raw, parser-friendly script when tts_script is missing."""
        if briefing_data is None:
            return []

        if date_str is None:
            date_str = self._kst_now().strftime("%Y%m%d")
        date_str_dash = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

        section_summaries = briefing_data.get("section_summaries", {}) or {}
        hojae = briefing_data.get("hojae", []) or []
        akjae = briefing_data.get("akjae", []) or []

        lines: list[str] = [
            f"Title: 오늘의 모닝뉴스 ({date_str_dash})",
            f"Date: {date_str_dash}",
            "Sections:",
        ]

        for key in ["정치", "경제/거시", "기업/산업", "부동산", "국제"]:
            summary = section_summaries.get(key, "").strip() if isinstance(section_summaries, dict) else ""
            lines.append(f"- {key}: {summary}")

        lines.append("Hojae:")
        if hojae:
            lines.extend([f"- {item}" for item in hojae])
        else:
            lines.append("- (none)")

        lines.append("Akjae:")
        if akjae:
            lines.extend([f"- {item}" for item in akjae])
        else:
            lines.append("- (none)")

        return lines

    def _build_tts_lines_from_source_script(self, source_script: dict | str | None) -> list[str]:
        """Flatten OpenAI source_script into a list of TTS lines.

        source_script is the master content. It can be either a plain text string
        (new format) or a structured dict (legacy format). This function flattens
        it and splits long sentences for better TTS readability.
        """
        if source_script is None:
            return []

        lines: list[str] = []

        def _split_long_line(text: str) -> list[str]:
            if not text:
                return []
            parts = re.split(r"(?<=[.!?。？！])\s+|,\s+|·\s+|그리고\s+|하지만\s+", text)
            cleaned = [p.strip() for p in parts if p and p.strip()]
            return cleaned if cleaned else [text.strip()]

        def _extend(part):
            if isinstance(part, list):
                for item in part:
                    text = str(item).strip()
                    if not text:
                        continue
                    lines.extend(_split_long_line(text))
            elif isinstance(part, str):
                value = part.strip()
                if value:
                    lines.extend(_split_long_line(value))

        if isinstance(source_script, str):
            paragraphs = [p.strip() for p in re.split(r"\n\s*\n", source_script) if p.strip()]
            for paragraph in paragraphs:
                sentence_chunks = re.split(r"(?<=[.!?。？！])\s+", paragraph)
                for chunk in sentence_chunks:
                    text = chunk.strip()
                    if not text:
                        continue
                    lines.extend(_split_long_line(text))
            return [line for line in lines if line]

        if not isinstance(source_script, dict):
            return []

        _extend(source_script.get("intro"))

        sections = source_script.get("sections", {})
        if not isinstance(sections, dict):
            sections = {}
        for key in ["정치", "경제/거시", "기업/산업", "부동산", "국제"]:
            _extend(sections.get(key))

        positive = source_script.get("positive", {})
        if isinstance(positive, dict):
            _extend(positive.get("theme"))
            _extend(positive.get("items"))

        negative = source_script.get("negative", {})
        if isinstance(negative, dict):
            _extend(negative.get("theme"))
            _extend(negative.get("items"))

        _extend(source_script.get("outro"))

        return [line for line in lines if line]

    def _pad_tts_lines(self, lines: list[str], target_min: int = 55, target_max: int = 75) -> list[str]:
        """Ensure TTS lines count falls within target range by splitting/padding."""
        if not lines:
            return lines
        # 최소 줄 수 강제는 비활성화: 뉴스가 적은 날은 짧게 허용
        if len(lines) > target_max:
            lines = lines[: target_max - 1] + [lines[-1]]

        return lines

    def _ensure_tts_outro(self, lines: list[str]) -> list[str]:
        """Force the last TTS line to the fixed outro."""
        if not lines:
            return lines
        outro = "오늘 뉴스 요약은 여기까지입니다. 내일 아침에 또 만나요."
        if lines[-1] != outro:
            lines[-1] = outro
        return lines

    def save_tts_script_text(self, briefing_data: dict, date_str: str | None = None) -> str | None:
        """Save TTS script to a text file and return its path."""
        if briefing_data is None:
            return None

        if date_str is None:
            date_str = self._kst_now().strftime("%Y%m%d")

        briefing_data = self._ensure_tts_script(briefing_data, date_str)
        tts_script = briefing_data.get("tts_script") or {}
        lines = tts_script.get("lines", [])
        if isinstance(lines, str):
            lines = [lines]
        if not isinstance(lines, list):
            lines = []

        brief_scripts = briefing_data.get("brief_scripts") if isinstance(briefing_data, dict) else None
        if isinstance(brief_scripts, dict):
            source_script = brief_scripts.get("source_script")
            regenerated = self._build_tts_lines_from_source_script(source_script)
            if regenerated:
                regenerated = self._pad_tts_lines(regenerated)
                regenerated = self._ensure_tts_outro(regenerated)
                lines = regenerated

        lines = [str(line).strip() for line in lines if str(line).strip()]

        filename = os.path.join(self.tts_dir, f"youtube_tts_{date_str}.txt")
        tmp_file = f"{filename}.tmp"

        pronunciations = tts_script.get("pronunciations", [])
        pronunciation_lines = []
        for item in pronunciations:
            term = item.get("term") if isinstance(item, dict) else None
            say = item.get("say") if isinstance(item, dict) else None
            if term and say:
                pronunciation_lines.append(f"- {term} -> {say}")

        content_parts = [
            f"Title: {tts_script.get('title', '')}",
            f"DurationSecTarget: {tts_script.get('duration_sec_target', 300)}",
        ]
        if pronunciation_lines:
            content_parts.append("Pronunciations:")
            content_parts.extend(pronunciation_lines)

        if lines:
            content_parts.append("TtsLines:")
            content_parts.extend(lines)
        else:
            content_parts.append("RawScript:")
            content_parts.extend(self._build_tts_fallback_content(briefing_data, date_str))

        content = "\n".join(content_parts).strip() + "\n"

        try:
            os.makedirs(self.tts_dir, exist_ok=True)
            with open(tmp_file, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp_file, filename)
            return filename
        except Exception as e:
            if os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except Exception:
                    pass
            print(f"⚠️ TTS 스크립트 저장 실패: {e}")
            return None

    def save_brief_scripts_json(self, brief_scripts: dict | None, date_str: str | None = None) -> str | None:
        """Save source/read scripts to a single JSON file and return its path."""
        if not brief_scripts or not isinstance(brief_scripts, dict):
            return None

        if date_str is None:
            date_str = self._kst_now().strftime("%Y%m%d")

        filename = os.path.join(self.brief_dir, f"brief_{date_str}.json")
        tmp_file = f"{filename}.tmp"
        payload = {
            "source_script": brief_scripts.get("source_script"),

        }

        try:
            os.makedirs(self.brief_dir, exist_ok=True)
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            os.replace(tmp_file, filename)
            return filename
        except Exception as e:
            if os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except Exception:
                    pass
            print(f"⚠️ 브리프 스크립트 저장 실패: {e}")
            return None

    def save_srt_script_json(self, source_script: dict | None, date_str: str | None = None) -> str | None:
        """Save source_script JSON for SRT use."""
        if not source_script or not isinstance(source_script, dict):
            return None

        if date_str is None:
            date_str = self._kst_now().strftime("%Y%m%d")

        filename = os.path.join(self.brief_dir, f"srt_{date_str}.json")
        tmp_file = f"{filename}.tmp"

        try:
            os.makedirs(self.brief_dir, exist_ok=True)
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(source_script, f, ensure_ascii=False, indent=2)
            os.replace(tmp_file, filename)
            return filename
        except Exception as e:
            if os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except Exception:
                    pass
            print(f"⚠️ SRT 스크립트 저장 실패: {e}")
            return None

    def save_tts_script_json(self, source_script: dict | None, date_str: str | None = None) -> str | None:
        """Save source_script JSON for reference (deprecated, kept for backward compatibility)."""
        if not source_script or not isinstance(source_script, dict):
            return None

        if date_str is None:
            date_str = self._kst_now().strftime("%Y%m%d")

        filename = os.path.join(self.brief_dir, f"tts_{date_str}.json")
        tmp_file = f"{filename}.tmp"

        try:
            os.makedirs(self.brief_dir, exist_ok=True)
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(source_script, f, ensure_ascii=False, indent=2)
            os.replace(tmp_file, filename)
            return filename
        except Exception as e:
            if os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except Exception:
                    pass
            print(f"⚠️ TTS JSON 스크립트 저장 실패: {e}")
            return None

    def _build_brief_prompt_from_context(self, context_lines: list[str]) -> str:
        """Build OpenAI brief prompt with escaped braces."""
        template = """
당신은 **한국어 라디오 모닝뉴스 앵커**입니다.

당신의 임무는 기사 요약이 아니라,
출근길에 라디오를 틀어둔 청취자가 자연스럽게 끝까지 들을 수 있는
5분 내외의 아침 뉴스 브리핑 원고를 작성하는 것입니다.

아래 입력은 이미 선별·요약된 뉴스 데이터입니다.
이 입력만 사용해 원고를 작성하세요.

절대 규칙:
- 기사 목록처럼 나열하지 마세요.
- 섹션 제목을 쓰지 마세요. (정치, 경제 같은 말 금지)
- 불릿, 번호, 목록형 문장 금지
- “~입니다, ~했습니다” 톤의 낭독체만 사용하세요.
- 한 문장은 너무 길지 않게, 말로 읽히는 리듬을 유지하세요.
- 같은 뉴스 소재를 두 번 이상 반복하지 마세요.

반드시 지켜야 할 구성 흐름:
1. 오프닝: 짧은 인사 + 오늘 뉴스의 큰 흐름 예고
2. 국내 주요 이슈: 정치·정책·행정 이슈를 하나의 흐름으로 연결 (사실 → 맥락 → 현재 분위기)
3. 경제·생활 체감 뉴스: 물가, 증시, 생활과 연결되는 이슈 (체감/분위기/반응 표현 활용)
4. 산업·기술 흐름: 반도체, 방산, AI 등은 경쟁 구도 중심으로 설명 (기업명 최소화)
5. 부동산·주거 이슈: 가격 나열 금지, 시장 심리/체감 중심
6. 국제·안보 이슈: 지역별 묶어 자연스럽게 연결 (긴장/변화/관측 표현 활용)
7. 클로징: 오늘 뉴스 핵심 한 문장 정리 + 내일 다시 만난다는 말

문장 작성 가이드:
- “~로 보입니다”
- “~라는 반응도 나옵니다”
- “분위기가 이어지고 있습니다”
- “체감상 변화가 크지 않다는 말도 나옵니다”
- “해석은 엇갈립니다”

팩트 + 해석 1줄은 허용됩니다.
의견·평가·예측 추가는 금지합니다.

출력 형식:
- 하나의 연속된 원고로 작성하세요.
- 줄바꿈은 문단 구분용으로만 사용하세요.
- 섹션 제목, 소제목, 구분자 사용 금지

Output JSON (JSON 형식만 허용):
{{
  "source_script": "원고 전체 텍스트"
}}

입력 데이터:
{input_data}
"""
        return template.format(input_data="\n".join(context_lines))

    def ensure_brief_scripts(self, briefing_data: dict, date_str: str | None = None, *, max_retries: int = 3) -> dict:
        """Ensure brief_scripts are generated using existing briefing data."""
        if briefing_data is None:
            raise ValueError("briefing_data is required")

        if date_str is None:
            date_str = self._kst_now().strftime("%Y%m%d")

        section_summaries = briefing_data.get("section_summaries", {}) or {}
        hojae = briefing_data.get("hojae", []) or []
        akjae = briefing_data.get("akjae", []) or []

        context_lines = ["섹션 요약:"]
        for key in ["정치", "경제/거시", "기업/산업", "부동산", "국제"]:
            summary = section_summaries.get(key, "") if isinstance(section_summaries, dict) else ""
            context_lines.append(f"- {key}: {summary}")
        if hojae:
            context_lines.append("호재:")
            context_lines.extend([f"- {item}" for item in hojae])
        if akjae:
            context_lines.append("악재:")
            context_lines.extend([f"- {item}" for item in akjae])

        brief_prompt = self._build_brief_prompt_from_context(context_lines)

        brief_data = self._generate_tts_script_with_openai(
            brief_prompt,
            model=config.openai_model_tts,
            max_retries=max_retries,
        )
        if isinstance(brief_data, dict) and isinstance(brief_data.get("source_script"), str):
            briefing_data = {**briefing_data}
            briefing_data["brief_scripts"] = {
                "source_script": brief_data.get("source_script"),
            }
            briefing_data.setdefault("meta", {})["brief_generated_by"] = "openai"
            return briefing_data

        raise ValueError("OpenAI brief script generation returned unexpected payload")

    def regenerate_tts_only(self, briefing_data: dict, date_str: str | None = None, *, max_retries: int = 3) -> dict:
        if briefing_data is None:
            raise ValueError("briefing_data is required for TTS-only regeneration")

        if date_str is None:
            date_str = self._kst_now().strftime("%Y%m%d")

        date_str_dash = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        kst_korean_date = self._format_korean_date(self._kst_now())

        section_summaries = briefing_data.get("section_summaries", {}) or {}
        hojae = briefing_data.get("hojae", []) or []
        akjae = briefing_data.get("akjae", []) or []

        context_lines = ["섹션 요약:"]
        for key in ["정치", "경제/거시", "기업/산업", "부동산", "국제"]:
            summary = section_summaries.get(key, "") if isinstance(section_summaries, dict) else ""
            context_lines.append(f"- {key}: {summary}")
        if hojae:
            context_lines.append("호재:")
            context_lines.extend([f"- {item}" for item in hojae])
        if akjae:
            context_lines.append("악재:")
            context_lines.extend([f"- {item}" for item in akjae])

        brief_prompt = self._build_brief_prompt_from_context(context_lines)

        brief_data = self._generate_tts_script_with_openai(
            brief_prompt,
            model=config.openai_model_tts,
            max_retries=max_retries,
        )
        if isinstance(brief_data, dict) and isinstance(brief_data.get("source_script"), str):
            briefing_data = {**briefing_data}
            briefing_data["brief_scripts"] = {
                "source_script": brief_data.get("source_script"),
            }
            briefing_data.setdefault("meta", {})["brief_generated_by"] = "openai"
            return briefing_data

        raise ValueError("OpenAI brief script generation returned unexpected payload")

    def analyze_sentiment(self, categorized_news, date_str=None, *, use_cache=True, allow_stale=True, max_retries: int = 3):
        """브리핑 + 호재/악재 생성.

        - use_cache=True: sentiment_cache/sentiment_YYYYMMDD.json이 있으면 Gemini 호출 없이 재사용
        - allow_stale=True: 당일 캐시가 없거나 Gemini 실패 시 최근 캐시를 대신 표시(브리핑 섹션이 사라지지 않도록)
        - max_retries: 503/UNAVAILABLE 등에 대해 exponential backoff 재시도
        """
        if not categorized_news:
            return self._fallback_briefing(error="no categorized_news")

        if date_str is None:
            date_str = self._kst_now().strftime("%Y%m%d")

        if use_cache:
            cached = self.load_cached_data(date_str)
            if cached is not None:
                print(f"✅ 감성/브리핑 캐시 재사용: {self.get_cache_filename(date_str)}")
                cached = self._ensure_tts_script(cached, date_str)
                brief_scripts_cached = cached.get("brief_scripts")
                if isinstance(brief_scripts_cached, dict):
                    openai_tts_lines = self._build_tts_lines_from_source_script(
                        brief_scripts_cached.get("source_script")
                    )
                    if openai_tts_lines:
                        openai_tts_lines = self._pad_tts_lines(openai_tts_lines)
                        openai_tts_lines = self._ensure_tts_outro(openai_tts_lines)
                        cached.setdefault("tts_script", {})
                        cached["tts_script"]["lines"] = openai_tts_lines
                        cached.setdefault("meta", {})["tts_lines_generated_by"] = "openai_source_script"
                        if isinstance(cached.get("meta"), dict):
                            cached["meta"].pop("tts_fallback", None)
                        cached = self._normalize_tts_script(cached, date_str)
                        if use_cache:
                            self.save_cached_data(cached, date_str)
                return cached

            # 캐시 재사용 모드인데 오늘 캐시가 없으면, Gemini 호출 없이 최신 캐시를 폴백으로 사용
            if allow_stale:
                stale_date, stale_path = self._find_latest_cache_file(exclude_date_str=date_str)
                if stale_path:
                    stale = self.load_cached_data(stale_date)
                    if stale is not None:
                        stale.setdefault("meta", {})
                        stale["meta"].update({
                            "generated_by": "stale_cache",
                            "source_date": stale_date,
                            "generated_at": datetime.now().isoformat(),
                        })
                        stale = self._ensure_tts_script(stale, date_str)
                        # 다음 실행부터는 당일 캐시로 바로 로드 가능하도록 저장
                        self.save_cached_data(stale, date_str)
                        print(f"✅ 오늘 캐시가 없어 최근 브리핑 캐시({stale_date})로 대체합니다.")
                        return stale

        # 현재 모드 확인
        current_mode = self.is_trading_day()
        is_first_day_after_holiday = self.is_first_trading_day_after_holiday()
        print(f"📊 현재 모드: {'평일 장 중' if current_mode == 'trading' else '주말/공휴일 누적'}")
        if is_first_day_after_holiday:
            print("📅 휴일 다음 날 모드: 통합 시그널 적용")

        # 브리핑용 전체 뉴스
        briefing_context = ""
        for category, items in categorized_news.items():
            if items:
                briefing_context += f"\n[{category}]\n"
                for item in items[:30]:
                    briefing_context += f"- {item['title']}\n"

        briefing_json_schema = """
{
  "section_summaries": {
    "정치": "...",
    "경제/거시": "...",
    "기업/산업": "...",
    "부동산": "...",
    "국제": "..."
  },
  "hojae": ["회사명: 사유"],
  "akjae": ["회사명: 사유"],
}
""".strip()

        kst_now = self._kst_now()
        date_str_dash = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        kst_korean_date = self._format_korean_date(kst_now)

        briefing_prompt = f"""
당신은 오늘의 뉴스 브리핑 작성자입니다. 오늘 분류된 뉴스 데이터를 바탕으로 간단히 읽기 좋은 아침 브리핑을 작성하세요.

필수 규칙:
1. 모든 답변은 한국어로 작성합니다.
2. 각 섹션의 요약은 있었던 사실과 분위기만 전달하고, 전망이나 판단은 하지 마세요.
3. 가능하면 긍정적 흐름과 부정적 이슈를 함께 담되 과도한 연결 없이 자연스럽고 읽기 쉬운 서술형으로 작성하세요.

수행 과제:
1. **모닝브리핑**: 본격적으로 뉴스를 읽기전에 오늘의 공기를 파악하기 위한 브리핑이므로 최대한 가독성 좋게 작성하세요.
2. **기업 감성 분석**: 주가에 '실질적'인 영향을 줄 수 있는 결정적인 호재(Hojae)와 악재(Akjae)를 찾으세요.
   - 호재 선정: 대규모 수주(수백억 원 이상), M&A, 핵심 기술 혁신, 실적 턴어라운드 (단순 인사나 소규모 협약은 제외).
   - 악재 선정: 어닝 쇼크, 법적 분쟁, 대규모 리콜, 자금 유동성 위기, 주요 생산 시설 사고.
   - 이유 표기: 각 기업 옆에 10자 이내의 아주 짧은 사유를 덧붙이세요.
   - 형식: "회사명: 사유"

TTS 스크립트 생성 규칙:
1. 5분 낭독 기준(4분30초~5분30초)으로 55~75줄 내외 작성.
2. 기사체 금지. 말하기체로 짧은 문장(한 줄=한 문장).
3. 섹션 전환 멘트 포함: "다음은…", "한편…", "정리하면…" 등.
4. 숫자/약어/단위는 TTS가 읽기 쉬운 형태로 변환하거나 pronunciations에 등록.
   - 예: "3.2%" → "삼쩜이 퍼센트", "1,200달러" → "천이백 달러"
5. 마지막 줄은 반드시 고정 문구 사용:
   "오늘 뉴스 요약은 여기까지입니다. 내일 아침에 또 만나요."
6. 첫 줄은 반드시 날짜를 포함해 아래 형식을 지키세요:
   "[SMILE] 좋은 아침입니다. {kst_korean_date} 모닝뉴스 시작합니다. [PAUSE 0.4]"
7. title은 반드시 "오늘의 모닝뉴스 ({date_str_dash})"로 설정하세요.

Output JSON Format:
{briefing_json_schema}

News List:
{briefing_context}
"""

        try:
            briefing_data = self._generate_json_with_retry(
                briefing_prompt,
                model=config.model_flash,
                max_retries=max_retries,
            )

            if not isinstance(briefing_data, dict):
                raise ValueError(f"Unexpected briefing_data type: {type(briefing_data)}")

            base_sections = {"정치": "", "경제/거시": "", "기업/산업": "", "부동산": "", "국제": ""}
            section_summaries = briefing_data.get("section_summaries")
            if not isinstance(section_summaries, dict):
                section_summaries = {}
            merged_sections = {**base_sections, **{k: v for k, v in section_summaries.items() if isinstance(k, str)}}
            briefing_data["section_summaries"] = merged_sections

            if not isinstance(briefing_data.get("hojae"), list):
                briefing_data["hojae"] = []
            if not isinstance(briefing_data.get("akjae"), list):
                briefing_data["akjae"] = []

            final_data = {
                **self._ensure_tts_script(briefing_data, date_str),
                "analysis_mode": current_mode,
                "is_holiday_next_day": is_first_day_after_holiday,
                "meta": {
                    "generated_by": "gemini",
                    "generated_at": datetime.now().isoformat(),
                },
            }

            brief_scripts_payload = None
            try:
                brief_context_lines = ["섹션 요약:"]
                for key in ["정치", "경제/거시", "기업/산업", "부동산", "국제"]:
                    summary = briefing_data.get("section_summaries", {}).get(key, "") if isinstance(briefing_data.get("section_summaries"), dict) else ""
                    brief_context_lines.append(f"- {key}: {summary}")
                if briefing_data.get("hojae"):
                    brief_context_lines.append("호재:")
                    brief_context_lines.extend([f"- {item}" for item in briefing_data.get("hojae", [])])
                if briefing_data.get("akjae"):
                    brief_context_lines.append("악재:")
                    brief_context_lines.extend([f"- {item}" for item in briefing_data.get("akjae", [])])

                brief_prompt = self._build_brief_prompt_from_context(brief_context_lines)
                brief_data = self._generate_tts_script_with_openai(
                    brief_prompt,
                    model=config.openai_model_tts,
                    max_retries=max_retries,
                )
                if isinstance(brief_data, dict) and isinstance(brief_data.get("source_script"), str):
                    brief_scripts_payload = {
                        "source_script": brief_data.get("source_script"),
                    }
                    final_data["brief_scripts"] = brief_scripts_payload
                    final_data.setdefault("meta", {})["brief_generated_by"] = "openai"
                    openai_tts_lines = self._build_tts_lines_from_source_script(
                        brief_scripts_payload.get("source_script")
                    )
                    if openai_tts_lines:
                        openai_tts_lines = self._pad_tts_lines(openai_tts_lines)
                        openai_tts_lines = self._ensure_tts_outro(openai_tts_lines)
                        final_data.setdefault("tts_script", {})
                        final_data["tts_script"]["lines"] = openai_tts_lines
                        final_data.setdefault("meta", {})["tts_lines_generated_by"] = "openai_source_script"
                        if isinstance(final_data.get("meta"), dict):
                            final_data["meta"].pop("tts_fallback", None)
            except Exception as e:
                print(f"⚠️ OpenAI 브리프 스크립트 생성 실패: {e}")
                final_data.setdefault("meta", {})["brief_generated_by"] = "gemini_fallback"

            final_data = self._normalize_tts_script(final_data, date_str)
            if not self._validate_tts_script(final_data, date_str):
                print("⚠️ TTS 스크립트 검증 실패: 재생성 시도")
                retry_prompt = briefing_prompt + "\n\n중요: 위 규칙을 반드시 지키세요. 날짜/줄 수를 위반하면 실패입니다."
                briefing_data = self._generate_json_with_retry(
                    retry_prompt,
                    model=config.model_flash,
                    max_retries=max_retries,
                )
                if not isinstance(briefing_data, dict):
                    raise ValueError(f"Unexpected briefing_data type after retry: {type(briefing_data)}")
                final_data = {
                    **self._ensure_tts_script(briefing_data, date_str),
                    "analysis_mode": current_mode,
                    "is_holiday_next_day": is_first_day_after_holiday,
                    "meta": {
                        "generated_by": "gemini_retry",
                        "generated_at": datetime.now().isoformat(),
                    },
                }
                if brief_scripts_payload:
                    final_data["brief_scripts"] = brief_scripts_payload
                    final_data.setdefault("meta", {})["brief_generated_by"] = "openai"
                    openai_tts_lines = self._build_tts_lines_from_source_script(
                        brief_scripts_payload.get("source_script")
                    )
                    if openai_tts_lines:
                        openai_tts_lines = self._pad_tts_lines(openai_tts_lines)
                        openai_tts_lines = self._ensure_tts_outro(openai_tts_lines)
                        final_data.setdefault("tts_script", {})
                        final_data["tts_script"]["lines"] = openai_tts_lines
                        final_data.setdefault("meta", {})["tts_lines_generated_by"] = "openai_source_script"
                        if isinstance(final_data.get("meta"), dict):
                            final_data["meta"].pop("tts_fallback", None)
                final_data = self._normalize_tts_script(final_data, date_str)

            if not self._validate_tts_script(final_data, date_str):
                print("⚠️ TTS 스크립트 검증 실패: OpenAI 기반 스크립트로 대체")
                if brief_scripts_payload:
                    openai_tts_lines = self._build_tts_lines_from_source_script(
                        brief_scripts_payload.get("source_script")
                    )
                    if openai_tts_lines:
                        openai_tts_lines = self._pad_tts_lines(openai_tts_lines)
                        openai_tts_lines = self._ensure_tts_outro(openai_tts_lines)
                        final_data.setdefault("tts_script", {})
                        final_data["tts_script"]["lines"] = openai_tts_lines
                        final_data.setdefault("meta", {})["tts_lines_generated_by"] = "openai_source_script"
                        if isinstance(final_data.get("meta"), dict):
                            final_data["meta"].pop("tts_fallback", None)
                        final_data = self._normalize_tts_script(final_data, date_str)
                if not self._validate_tts_script(final_data, date_str):
                    print("⚠️ TTS 스크립트 검증 실패: 폴백 스크립트로 대체")
                    final_data = self._apply_tts_fallback(final_data, date_str)
                if brief_scripts_payload:
                    final_data["brief_scripts"] = brief_scripts_payload
                    final_data.setdefault("meta", {})["brief_generated_by"] = "openai"

            # 휴일 다음 날이면 캐시 병합 및 통합 리포트
            if is_first_day_after_holiday:
                print("🔄 휴일 다음 날: 캐시 데이터 통합 중...")
                final_data = self._merge_holiday_cache(final_data)
                self._clear_holiday_cache()

            # 누적 모드일 경우 캐시 병합
            if current_mode == 'accumulation':
                cached_data = self.load_cached_data(date_str)
                if cached_data:
                    print("🔄 캐시된 데이터와 병합 중...")
                    final_data = self.merge_sentiment_data(final_data, cached_data)

            # 성공 시에는 모드와 무관하게 당일 캐시 저장(재사용 시간대에 Gemini 호출 방지)
            if use_cache:
                self.save_cached_data(final_data, date_str)

            return final_data

        except Exception as e:
            print(f"Error generating sentiment analysis: {e}")

            # stale cache fallback
            if allow_stale:
                stale_date, stale_path = self._find_latest_cache_file(exclude_date_str=date_str)
                if stale_path:
                    stale = self.load_cached_data(stale_date)
                    if stale is not None:
                        stale.setdefault("meta", {})
                        stale["meta"].update({
                            "generated_by": "stale_cache",
                            "error": str(e),
                            "source_date": stale_date,
                            "generated_at": datetime.now().isoformat(),
                        })
                        stale = self._ensure_tts_script(stale, date_str)
                        # 저장해두면 다음 실행에서 당일 캐시로 바로 로드 가능
                        if use_cache:
                            self.save_cached_data(stale, date_str)
                        return stale

            return self._fallback_briefing(error=str(e))

    def _normalize_tts_script(self, data: dict, date_str: str) -> dict:
        if not data:
            return data

        kst_now = self._kst_now()
        date_str_dash = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        kst_korean_date = self._format_korean_date(kst_now)

        tts_script = data.get("tts_script") or {}
        tts_script["title"] = f"오늘의 모닝뉴스 ({date_str_dash})"

        lines = tts_script.get("lines", [])
        if isinstance(lines, str):
            lines = [lines]
        if not isinstance(lines, list):
            lines = []

        intro = f"[SMILE] 좋은 아침입니다. {kst_korean_date} 모닝뉴스 시작합니다. [PAUSE 0.4]"
        if lines:
            lines[0] = intro
        else:
            lines = [intro]

        tts_script["lines"] = [str(line).strip() for line in lines if str(line).strip()]
        data["tts_script"] = tts_script
        return data

    def _validate_tts_script(self, data: dict, date_str: str) -> bool:
        if not data:
            return False

        tts_script = data.get("tts_script") or {}
        title = tts_script.get("title", "")
        lines = tts_script.get("lines", [])
        if isinstance(lines, str):
            lines = [lines]
        if not isinstance(lines, list):
            return False

        date_str_dash = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        kst_korean_date = self._format_korean_date(self._kst_now())

        if date_str_dash not in title:
            return False

        if not lines:
            return False

        if kst_korean_date not in lines[0]:
            return False

        line_count = len(lines)
        if line_count < 1:
            return False
        if line_count > 75:
            return False

        return True

    def _apply_tts_fallback(self, data: dict, date_str: str) -> dict:
        if not data:
            data = {}

        kst_now = self._kst_now()
        date_str_dash = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        kst_korean_date = self._format_korean_date(kst_now)

        intro = f"[SMILE] 좋은 아침입니다. {kst_korean_date} 모닝뉴스 시작합니다. [PAUSE 0.4]"
        outro = "오늘 뉴스 요약은 여기까지입니다. 내일 아침에 또 만나요."

        tts_script = data.get("tts_script") or {}
        lines = tts_script.get("lines", [])
        if isinstance(lines, str):
            lines = [lines]
        if not isinstance(lines, list):
            lines = []

        core_lines = [line for line in lines[1:] if isinstance(line, str)]
        core_lines = [line for line in core_lines if line.strip() and line.strip() != outro]
        if not core_lines:
            core_lines = [
                "오늘의 주요 뉴스 흐름을 정리해 드립니다.",
                "정치권에서는 지역 순회 일정과 정책 논의가 이어졌습니다.",
                "경제는 외국인 수급과 환율 변동이 동시에 주목받았습니다.",
                "기업 현장에서는 반도체 투자 확대와 실적 발표가 화두였습니다.",
                "부동산 시장은 매물 증가로 가격 상승세가 다소 진정되었습니다.",
                "해외는 지정학적 변수와 미국 정치 이슈가 혼재했습니다.",
            ]

        target_lines = [intro]
        target_lines.extend(core_lines)
        target_lines.append(outro)

        # pad or trim to 55 lines
        while len(target_lines) < 55:
            target_lines.insert(-1, "주요 이슈를 차분히 확인해 보시기 바랍니다.")
        if len(target_lines) > 75:
            target_lines = target_lines[:74] + [outro]

        tts_script["title"] = f"오늘의 모닝뉴스 ({date_str_dash})"
        tts_script["lines"] = target_lines
        data["tts_script"] = tts_script
        data.setdefault("meta", {})
        data["meta"].update({
            "tts_fallback": True,
            "generated_at": datetime.now().isoformat(),
        })
        return data
    
    def _merge_holiday_cache(self, current_data):
        """
        휴일 다음 날에 캐시된 모든 데이터를 병합
        """
        now = datetime.now()
        merged_data = {
            **current_data,
            "hojae": [],
            "akjae": [],
            "holiday_merged_dates": []
        }
        
        # 최근 3일간의 캐시 데이터 수집
        for i in range(1, 4):  # 1일전, 2일전, 3일전
            past_date = now - timedelta(days=i)
            date_str = past_date.strftime("%Y%m%d")
            cached_data = self.load_cached_data(date_str)
            
            if cached_data:
                merged_data["holiday_merged_dates"].append(date_str)
                
                # 호재 데이터 병합
                for item in cached_data.get("hojae", []):
                    if item not in merged_data["hojae"]:
                        merged_data["hojae"].append(item)
                
                # 악재 데이터 병합
                for item in cached_data.get("akjae", []):
                    if item not in merged_data["akjae"]:
                        merged_data["akjae"].append(item)
        
        # 현재 데이터 추가
        merged_data["hojae"].extend(current_data.get("hojae", []))
        merged_data["akjae"].extend(current_data.get("akjae", []))
        
        # 중복 제거
        merged_data["hojae"] = list(set(merged_data["hojae"]))
        merged_data["akjae"] = list(set(merged_data["akjae"]))
        
        print(f"✅ 휴일 데이터 통합 완료: {len(merged_data['holiday_merged_dates'])}일간 데이터 병합")
        
        return merged_data
    
    def _clear_holiday_cache(self):
        """
        휴일 캐시 정리
        """
        now = datetime.now()
        
        # 최근 3일간 캐시 파일 정리
        for i in range(1, 4):
            past_date = now - timedelta(days=i)
            date_str = past_date.strftime("%Y%m%d")
            cache_file = self.get_cache_filename(date_str)
            
            if os.path.exists(cache_file):
                try:
                    os.remove(cache_file)
                    print(f"🗑️ 캐시 파일 정리: {cache_file}")
                except Exception as e:
                    print(f"캐시 파일 정리 실패: {e}")
    
    def generate_weekend_summary(self):
        """
        주말에 쌓인 데이터를 월요일 아침에 한 번에 출력
        Returns: 주말 종합 요약 데이터
        """
        print("📅 주말 데이터 종합 분석 시작...")
        
        # 주말 날짜 계산 (금요일부터 일요일까지)
        now = datetime.now()
        
        # 월요일인지 확인
        if now.weekday() != 0:  # 0은 월요일
            print("⚠️ 월요일이 아니어서 주말 요약을 생성할 수 없습니다.")
            return None
        
        # 주말 날짜들 계산
        friday = now - timedelta(days=3)
        saturday = now - timedelta(days=2) 
        sunday = now - timedelta(days=1)
        
        weekend_dates = [
            friday.strftime("%Y%m%d"),
            saturday.strftime("%Y%m%d"),
            sunday.strftime("%Y%m%d")
        ]
        
        print(f"📊 분석 대상 주말: {friday.strftime('%m/%d')}~{sunday.strftime('%m/%d')}")
        
        # 주말 데이터 수집
        weekend_data = []
        for date_str in weekend_dates:
            cached_data = self.load_cached_data(date_str)
            if cached_data:
                cached_data["date"] = date_str
                weekend_data.append(cached_data)
        
        if not weekend_data:
            print("📭 주말 데이터가 없습니다.")
            return None
        
        # 주말 데이터 종합 분석
        summary = self._analyze_weekend_data(weekend_data)
        
        return summary
    
    def _analyze_weekend_data(self, weekend_data):
        """
        주말 데이터를 종합 분석하여 요약 생성
        """
        print("🔍 주말 데이터 종합 분석 중...")
        
        # 모든 호재/악재 데이터 수집
        all_hojae = {}
        all_akjae = {}
        
        for day_data in weekend_data:
            date_str = day_data.get("date", "")
            
            # 호재 데이터 처리
            for item in day_data.get("hojae", []):
                if ":" in item:
                    company, reason = item.split(":", 1)
                    company = company.strip()
                    
                    if company not in all_hojae:
                        all_hojae[company] = {
                            "reasons": [],
                            "dates": [],
                            "count": 0
                        }
                    
                    all_hojae[company]["reasons"].append(reason.strip())
                    all_hojae[company]["dates"].append(date_str)
                    all_hojae[company]["count"] += 1
            
            # 악재 데이터 처리
            for item in day_data.get("akjae", []):
                if ":" in item:
                    company, reason = item.split(":", 1)
                    company = company.strip()
                    
                    if company not in all_akjae:
                        all_akjae[company] = {
                            "reasons": [],
                            "dates": [],
                            "count": 0
                        }
                    
                    all_akjae[company]["reasons"].append(reason.strip())
                    all_akjae[company]["dates"].append(date_str)
                    all_akjae[company]["count"] += 1
        
        # 주말 요약 생성
        summary = {
            "weekend_dates": [data.get("date", "") for data in weekend_data],
            "hojae_summary": [],
            "akjae_summary": [],
            "top_hojae": [],
            "top_akjae": [],
            "total_hojae": len(all_hojae),
            "total_akjae": len(all_akjae)
        }
        
        # 호재 요약 (회사별로 그룹화)
        for company, data in sorted(all_hojae.items(), key=lambda x: x[1]["count"], reverse=True):
            summary["hojae_summary"].append({
                "company": company,
                "count": data["count"],
                "reasons": data["reasons"],
                "dates": data["dates"]
            })
        
        # 악재 요약
        for company, data in sorted(all_akjae.items(), key=lambda x: x[1]["count"], reverse=True):
            summary["akjae_summary"].append({
                "company": company,
                "count": data["count"],
                "reasons": data["reasons"],
                "dates": data["dates"]
            })
        
        # 상위 호재/악재 (3회 이상 언급된 기업)
        summary["top_hojae"] = [item for item in summary["hojae_summary"] if item["count"] >= 3]
        summary["top_akjae"] = [item for item in summary["akjae_summary"] if item["count"] >= 3]
        
        print(f"✅ 주말 요약 완료: 호재 {len(all_hojae)}개, 악재 {len(all_akjae)}개")
        
        return summary
    
    def format_weekend_summary_message(self, weekend_summary):
        """
        주말 요약을 텔레그램 메시지로 포맷팅
        """
        if not weekend_summary:
            return None
        
        dates = weekend_summary.get("weekend_dates", [])
        if dates:
            date_range = f"{dates[-1][-4:]}-{dates[-1][4:6]}-{dates[-1][6:8]} ~ {dates[0][-4:]}-{dates[0][4:6]}-{dates[0][6:8]}"
        else:
            date_range = "주말"
        
        lines = [
            f"📊 주말 종합 뉴스 요약 ({date_range})",
            "",
            f"📈 호재 기업: {weekend_summary.get('total_hojae', 0)}개",
            f"📉 악재 기업: {weekend_summary.get('total_akjae', 0)}개",
            ""
        ]
        
        # 상위 호재 기업
        top_hojae = weekend_summary.get("top_hojae", [])
        if top_hojae:
            lines.append("🔥 주요 호재 기업:")
            for item in top_hojae[:5]:  # 상위 5개
                lines.append(f"  • {item['company']}: {item['count']}회")
            lines.append("")
        
        # 상위 악재 기업
        top_akjae = weekend_summary.get("top_akjae", [])
        if top_akjae:
            lines.append("⚠️ 주요 악재 기업:")
            for item in top_akjae[:5]:  # 상위 5개
                lines.append(f"  • {item['company']}: {item['count']}회")
            lines.append("")
        
        lines.append("📱 자세한 내용은 웹사이트에서 확인하세요!")
        
        return "\n".join(lines)

    # NOTE: 과거에 analyze_sentiment()가 파일 내에 2번 정의되어 아래쪽이 위 로직을 덮어쓰던 문제가 있었음.
    # 현재는 위의 analyze_sentiment() 하나만 유지합니다.

    def extract_hojae_list(self, briefing_data):
        """
        Extract hojae list from briefing data.
        Returns a list of hojae items.
        """
        if not briefing_data:
            return []
        
        return briefing_data.get("hojae", [])

    def extract_akjae_list(self, briefing_data):
        """
        Extract akjae list from briefing data.
        Returns a list of akjae items.
        """
        if not briefing_data:
            return []
        
        return briefing_data.get("akjae", [])

    def get_hojae_count(self, briefing_data):
        """
        Get the count of hojae items.
        """
        return len(self.extract_hojae_list(briefing_data))

    def get_akjae_count(self, briefing_data):
        """
        Get the count of akjae items.
        """
        return len(self.extract_akjae_list(briefing_data))

    def format_telegram_message(self, briefing_data, date_str=None, total_news_count=None):
        """
        Format telegram message for hojae notification.
        Returns a formatted message string.
        """
        hojae_list = self.extract_hojae_list(briefing_data)
        hojae_count = len(hojae_list)
        
        if not hojae_list:
            return None
        
        # Compose summary header (date, total news, hojae count)
        headline = "📰 모닝뉴스가 업데이트되었습니다"
        if date_str:
            headline += f" ({date_str})"

        summary_parts = []
        if total_news_count is not None:
            summary_parts.append(f"총 {total_news_count}건의 뉴스")
        summary_parts.append(f"호재 기업: {hojae_count}곳")
        summary_line = " / ".join(summary_parts)

        list_title = f"📈 호재 기업 리스트 ({date_str})" if date_str else "📈 호재 기업 리스트"

        lines = [headline, summary_line, "", list_title]
        for item in hojae_list:
            lines.append(f"- {item}")
        message = "\n".join(lines)
        
        return message

    def get_section_summaries(self, briefing_data):
        """
        Extract section summaries from briefing data.
        """
        if not briefing_data:
            return {}
        
        return briefing_data.get("section_summaries", {})

    def has_sentiment_data(self, briefing_data):
        """
        Check if briefing data contains sentiment analysis (hojae/akjae).
        """
        if not briefing_data:
            return False
        
        return bool(briefing_data.get("hojae") or briefing_data.get("akjae"))

if __name__ == "__main__":
    # Test the SentimentAnalyzer
    analyzer = SentimentAnalyzer()
    
    print("🧪 SentimentAnalyzer 테스트 시작...")
    
    # 테스트 1: 날짜 판단 로직
    print(f"📅 현재 모드: {analyzer.is_trading_day()}")
    
    # 테스트 2: 캐시 기능
    test_data = {
        "hojae": ["삼성전자: 반도체 호재", "LG화학: 배터리 호재"],
        "akjae": ["현대차: 리콜 악재"],
        "section_summaries": {"정치": "테스트 요약"}
    }
    
    analyzer.save_cached_data(test_data, "20260117")
    loaded_data = analyzer.load_cached_data("20260117")
    print(f"✅ 캐시 테스트: {'성공' if loaded_data else '실패'}")
    
    # 테스트 3: 데이터 병합
    current_data = {
        "hojae": ["삼성전자: 신제품 출시", "SK하이닉스: 수주"],
        "akjae": ["현대차: 리콜 악재", "기아: 부품 결함"]
    }
    
    merged = analyzer.merge_sentiment_data(current_data, test_data)
    print(f"✅ 병합 테스트: 호재 {len(merged['hojae'])}개, 악재 {len(merged['akjae'])}개")
    
    # 테스트 4: 주말 요약 (월요일이 아니면 None 반환)
    weekend_summary = analyzer.generate_weekend_summary()
    print(f"📅 주말 요약 테스트: {'성공' if weekend_summary else '월요일이 아님'}")
    
    print("🎉 모든 테스트 완료!")
