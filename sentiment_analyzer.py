from google import genai
import json
import os
from datetime import datetime, timedelta
from config import config

class SentimentAnalyzer:
    def __init__(self):
        self.client = genai.Client(api_key=config.gemini_api_key)
        self.cache_dir = "sentiment_cache"
        os.makedirs(self.cache_dir, exist_ok=True)
        
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
            date_str = datetime.now().strftime("%Y%m%d")
        return os.path.join(self.cache_dir, f"sentiment_{date_str}.json")
    
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
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"✅ 감성 데이터 캐시 저장: {cache_file}")
        except Exception as e:
            print(f"캐시 저장 실패: {e}")
    
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
    
    def analyze_sentiment(self, categorized_news):
        """
        Generates a briefing summary and sentiment analysis (Good/Bad news).
        This replaces the original generate_briefing method from AIProcessor.
        """
        if not categorized_news:
            return None
            
        # 현재 모드 확인
        current_mode = self.is_trading_day()
        is_first_day_after_holiday = self.is_first_trading_day_after_holiday()
        
        print(f"📊 현재 모드: {'평일 장 중' if current_mode == 'trading' else '주말/공휴일 누적'}")
        if is_first_day_after_holiday:
            print(f"📅 휴일 다음 날 모드: 통합 시그널 적용")
        
        # 브리핑용 전체 뉴스 (24시간 범위)
        briefing_context = ""
        for category, items in categorized_news.items():
            if items:
                briefing_context += f"\n[{category}]\n"
                for item in items[:30]: 
                    briefing_context += f"- {item['title']}\n"
        
        # 매매봇용 필터링된 뉴스 (장외 뉴스 가중치)
        trading_news = self.filter_trading_signals(categorized_news)
        trading_context = ""
        for category, items in trading_news.items():
            if items:
                trading_context += f"\n[{category}]\n"
                for item in items[:30]: 
                    weight = item.get('time_weight', 1.0)
                    trading_context += f"- [{weight}x] {item['title']}\n"
        
        # 브리핑용 프롬프트
        briefing_prompt = f"""
        당신은 시니어 금융 분석가입니다. 오늘 분류된 뉴스 데이터를 바탕으로 심도 있는 아침 브리핑을 작성하세요.

        필수 규칙:
        1. 모든 답변은 한국어로 작성합니다.
        2. 각 섹션의 요약은 "사실 - 영향 - 체크포인트" 구조를 한 문장으로 유기적으로 연결하여 작성하세요.

        수행 과제:
        1. **섹션별 요약**: 각 섹션의 핵심 흐름을 날카롭게 요약하세요.
            - 형식 : "[사실] ~라는 소식이 있으나, [영향] 이로 인해 ~가 예상되므로, [체크포인트] 향후 ~를 주목해야 함."
            - 예시: "[사실] 미 연준의 금리 동결 발표가 있었으나, [영향] 시장은 여전히 하반기 인하 기대감을 유지하고 있어, [체크포인트] 다가올 소비자물가지수(CPI) 발표 수치를 예의주시해야 함."
        2. **기업 감성 분석**: 주가에 '실질적'인 영향을 줄 수 있는 결정적인 호재(Hojae)와 악재(Akjae)를 찾으세요.
           - 호재 선정: 대규모 수주(수백억 원 이상), M&A, 핵심 기술 혁신, 실적 턴어라운드 (단순 인사나 소규모 협약은 제외).
           - 악재 선정: 어닝 쇼크, 법적 분쟁, 대규모 리콜, 자금 유동성 위기, 주요 생산 시설 사고.
           - 이유 표기: 각 기업 옆에 10자 이내의 아주 짧은 사유를 덧붙이세요.
           - 형식: "회사명: 사유"
        
        Output JSON Format:
        {{
            "section_summaries": {{
                "정치": "...",
                "경제/거시": "...",
                "기업/산업": "...",
                "부동산": "...",
                "국제": "..."
            }},
            "hojae": ["회사명: 사유", "회사명: 사유"],
            "akjae": ["회사명: 사유", "회사명: 사유"]
        }}
        
        News List:
        {briefing_context}
        """
        
        # 매매봇용 프롬프트 (가중치 적용)
        trading_prompt = f"""
        당신은 매매봇 전문가입니다. 다음 뉴스 중에서 오늘의 매매에 실질적인 영향을 줄 수 있는 호재/악재만 선별해주세요.

        중요 규칙:
        1. [2.0x] 표시된 장외 뉴스(어제 15:30~오늘 08:30)를 최우선으로 고려하세요.
        2. [1.0x] 장중 뉴스는 이미 주가에 반영되었을 가능성이 높으므로 신중하게 판단하세요.
        3. 오늘의 매매 전략에 혼선을 줄 수 있는 뉴스는 제외하세요.

        선별 기준:
        - 호재: 장외 시간에 발생한 대규모 수주, M&A, 실적 턴어라운드, 핵심 기술 뉴스
        - 악재: 장외 시간에 발생한 어닝 쇼크, 법적 분쟁, 리콜, 유동성 위기

        Output JSON Format:
        {{
            "trading_hojae": ["회사명: 사유", "회사명: 사유"],
            "trading_akjae": ["회사명: 사유", "회사명: 사유"]
        }}
        
        Weighted News List:
        {trading_context}
        """
        
        try:
            # 브리핑 분석
            briefing_response = self.client.models.generate_content(
                model=config.model_flash,
                contents=briefing_prompt,
                config={'response_mime_type': 'application/json'}
            )
            briefing_data = json.loads(briefing_response.text)
            
            # 매매봇용 분석
            trading_response = self.client.models.generate_content(
                model=config.model_flash,
                contents=trading_prompt,
                config={'response_mime_type': 'application/json'}
            )
            trading_data = json.loads(trading_response.text)
            
            # 두 데이터 병합
            final_data = {
                **briefing_data,
                "trading_hojae": trading_data.get("trading_hojae", []),
                "trading_akjae": trading_data.get("trading_akjae", []),
                "analysis_mode": current_mode,
                "is_holiday_next_day": is_first_day_after_holiday
            }
            
            # 휴일 다음 날이면 캐시 병합 및 통합 리포트
            if is_first_day_after_holiday:
                print("🔄 휴일 다음 날: 캐시 데이터 통합 중...")
                final_data = self._merge_holiday_cache(final_data)
                self._clear_holiday_cache()
            
            # 누적 모드일 경우 캐시 저장
            elif current_mode == 'accumulation':
                today = datetime.now().strftime("%Y%m%d")
                cached_data = self.load_cached_data(today)
                
                if cached_data:
                    print(f"🔄 캐시된 데이터와 병합 중...")
                    merged_data = self.merge_sentiment_data(final_data, cached_data)
                    self.save_cached_data(merged_data, today)
                    return merged_data
                else:
                    self.save_cached_data(final_data, today)
                    return final_data
            else:
                # 평일 장 중 모드는 그대로 반환
                return final_data
                
        except Exception as e:
            print(f"Error generating sentiment analysis: {e}")
            return None
    
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

    def analyze_sentiment(self, categorized_news):
        """
        Generates a briefing summary and sentiment analysis (Good/Bad news).
        This replaces the original generate_briefing method from AIProcessor.
        """
        if not categorized_news:
            return None
            
        # Context preparation: Flatten the list but keep categories
        context = ""
        for category, items in categorized_news.items():
            if items:
                context += f"\n[{category}]\n"
                # Increase context to top 30 to catch more diverse news (like Akjae)
                for item in items[:30]: 
                    context += f"- {item['title']}\n"
        
        prompt = f"""
        당신은 시니어 금융 분석가입니다. 오늘 분류된 뉴스 데이터를 바탕으로 심도 있는 아침 브리핑을 작성하세요.

        필수 규칙:
        1. 모든 답변은 한국어로 작성합니다.
        2. 각 섹션의 요약은 "사실 - 영향 - 체크포인트" 구조를 한 문장으로 유기적으로 연결하여 작성하세요.

        수행 과제:
        1. **섹션별 요약**: 각 섹션의 핵심 흐름을 날카롭게 요약하세요.
            - 형식 : "[사실] ~라는 소식이 있으나, [영향] 이로 인해 ~가 예상되므로, [체크포인트] 향후 ~를 주목해야 함."
            - 예시: "[사실] 미 연준의 금리 동결 발표가 있었으나, [영향] 시장은 여전히 하반기 인하 기대감을 유지하고 있어, [체크포인트] 다가올 소비자물가지수(CPI) 발표 수치를 예의주시해야 함."
        2. **기업 감성 분석**: 주가에 '실질적'인 영향을 줄 수 있는 결정적인 호재(Hojae)와 악재(Akjae)를 찾으세요.
           - 호재 선정: 대규모 수주(수백억 원 이상), M&A, 핵심 기술 혁신, 실적 턴어라운드 (단순 인사나 소규모 협약은 제외).
           - 악재 선정: 어닝 쇼크, 법적 분쟁, 대규모 리콜, 자금 유동성 위기, 주요 생산 시설 사고.
           - 이유 표기: 각 기업 옆에 10자 이내의 아주 짧은 사유를 덧붙이세요.
           - 형식: "회사명: 사유"
        
        Output JSON Format:
        {{
            "section_summaries": {{
                "정치": "...",
                "경제/거시": "...",
                "기업/산업": "...",
                "부동산": "...",
                "국제": "..."
            }},
            "hojae": ["회사명: 사유", "회사명: 사유"],
            "akjae": ["회사명: 사유", "회사명: 사유"]
        }}
        
        News List:
        {context}
        """
        
        try:
            response = self.client.models.generate_content(
                model=config.model_flash,
                contents=prompt,
                config={'response_mime_type': 'application/json'}
            )
            return json.loads(response.text)
        except Exception as e:
            print(f"Error generating sentiment analysis: {e}")
            return None

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
