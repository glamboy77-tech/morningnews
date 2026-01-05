from google import genai
import json
import re
from difflib import SequenceMatcher
from config import config

class AIProcessor:
    def __init__(self):
        self.client = genai.Client(api_key=config.gemini_api_key)

    @staticmethod
    def _normalize_title(title: str) -> str:
        # Lowercase, remove punctuation, collapse whitespace for stable similarity checks
        cleaned = re.sub(r"[^\w\s]", " ", title.lower())
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    @staticmethod
    def _looks_like_same_event(main_item: dict, candidate: dict) -> bool:
        """Conservatively judge whether two articles describe the same event."""
        main_title = main_item.get('title', '')
        cand_title = candidate.get('title', '')
        if not main_title or not cand_title:
            return False

        norm_main = AIProcessor._normalize_title(main_title)
        norm_cand = AIProcessor._normalize_title(cand_title)

        # Quick reject on very short titles after cleanup
        if len(norm_main) < 10 or len(norm_cand) < 10:
            return False

        ratio = SequenceMatcher(None, norm_main, norm_cand).ratio()

        # Token overlap check to prevent broad-topic grouping
        main_tokens = set(norm_main.split())
        cand_tokens = set(norm_cand.split())
        overlap = len(main_tokens & cand_tokens)
        token_threshold = max(2, min(len(main_tokens), len(cand_tokens)) // 2)

        # Optional: reject if timestamps are far apart (> 36h) when both present
        if main_item.get('published_dt') and candidate.get('published_dt'):
            delta = abs((main_item['published_dt'] - candidate['published_dt']).total_seconds())
            if delta > 36 * 3600:
                return False

        return ratio >= 0.82 or (ratio >= 0.72 and overlap >= token_threshold)
    
    def process_domestic_news(self, news_items):
        """
        Takes a list of news items and returns a categorized dictionary with grouped duplicates.
        """
        if not news_items:
            return {}
            
        news_input = []
        for idx, item in enumerate(news_items):
            # Calculate priority score based on keywords
            score = 0
            for kw in config.target_keywords:
                if kw in item['title'] or kw in item.get('description', ''):
                    score += 5
            item['priority_score'] = score
            
            # Include description for better context
            desc = item.get('description', '')[:100] if item.get('description') else ''
            news_input.append(f"ID:{idx} | Source:{item['source']} | Title:{item['title']} | Desc:{desc}")
            
        news_text = "\n".join(news_input)
        
        prompt = f"""
        당신은 모닝뉴스봇의 전문 뉴스 분류기입니다. 아래 규칙대로 처리하세요.

        1단계: 필터링 (포용적)
        - ❌ 제외: 연예/가십, 영화, 경기 스코어만 있는 스포츠
        - ✅ 포함: 모든 비즈니스·정책·경제·산업·기업·금융 관련 뉴스
        - ✅ 포함: 경제, 정치, 기업, 부동산, 국제 관련 뉴스 전반
        - 의심스러울 때는 포함(KEEP)합니다.

        2단계: 카테고리 분류 (하나만 선택)
        - 정치: 정부, 정당, 선거, 입법
          · 정책/법안, 외교/안보, 거시 흐름에 집중
          · 시장/제도에 영향을 줄 뉴스 우선
        - 경제/거시: 거시경제, 정책, 물가/금리, 금융시장
        - 기업/산업: 기업, 산업, 비즈니스 거래, 실적
        - 부동산: 주택, 부동산 정책, 건설
        - 국제: 해외 뉴스, 국제 관계, 글로벌 이벤트

        기업/산업 기사에는 섹터를 지정하세요.
        - AI/로봇
        - 반도체
        - 자동차
        - 배터리/에너지
        - 바이오/제약
        - 조선해양
        - 금융
        - 통신/IT
        - 유통/소매
        - 건설
        - 화학/소재
        - 기타산업

        정치 기사에는 세부 분류를 지정하세요.
        - 정상/외교: 정상회담, 외교, 북핵/안보, 국제 관계
        - 당내 정국: 당내 갈등, 인사, 쇄신, 지도부 교체
        - 사법/의혹: 수사, 재판, 의혹, 공천 관련 의혹
        - 지방/통합: 지방 선거/출마, 지역 통합·행정구역 이슈
        - 입법/정책: 법안, 규제, 정책, 행정 명령/지침
        - 기타: 위에 해당하지 않는 정치 뉴스

        3단계: 중복 병합 (매우 엄격)
        세 조건을 모두 만족할 때만 중복으로 묶습니다.
        1) 동일 주체(회사/인물/조직), 2) 동일 사건, 3) 동일 일자

        출력(JSON):
        {
            "정치": [
                {"id": 0, "pol_subcategory": "정상/외교", "related_article_ids": [1, 2]},
                {"id": 5, "pol_subcategory": "입법/정책", "related_article_ids": []}
            ],
            "경제/거시": [...],
            "기업/산업": [
                {"id": 10, "sector": "반도체", "related_article_ids": [11]},
                {"id": 15, "sector": "자동차", "related_article_ids": []}
            ],
            "부동산": [...],
            "국제": [...]
        }

        - id: 대표 기사 ID
        - sector: 기업/산업에서만 사용. 위 섹터 목록 중 하나
        - related_article_ids: 동일 사건의 다른 기사 ID들

        입력 뉴스:
        {news_text}
        """
        
        try:
            response = self.client.models.generate_content(
                model=config.model_flash,
                contents=prompt,
                config={'response_mime_type': 'application/json'}
            )
            
            categorized_data = json.loads(response.text)
            
            # Map of possible AI outputs to our canonical keys
            category_map = {
                "정치": "정치", "Politics": "정치",
                "경제/거시": "경제/거시", "Economy/Macro": "경제/거시", "Economy": "경제/거시",
                "기업/산업": "기업/산업", "Corporate/Industry": "기업/산업", "Corporate": "기업/산업", "Industry": "기업/산업",
                "부동산": "부동산", "Real Estate": "부동산",
                "국제": "국제", "International": "국제"
            }
            
            final_result = {
                "정치": [],
                "경제/거시": [],
                "기업/산업": [],
                "부동산": [],
                "국제": []
            }
            
            for ai_category, groups in categorized_data.items():
                canonical_category = category_map.get(ai_category)
                if canonical_category and canonical_category in final_result:
                    for group in groups:
                        main_id = group.get('id')
                        if main_id is not None and 0 <= main_id < len(news_items):
                            item = news_items[main_id].copy()
                            
                            # Add sector info for Corporate/Industry articles
                            if canonical_category == "기업/산업":
                                item['sector'] = group.get('sector', '기타산업')

                            # Add subcategory info for Politics articles
                            if canonical_category == "정치":
                                item['pol_subcategory'] = group.get('pol_subcategory', '기타')

                            # Process related sources with links
                            related_id_list = group.get('related_article_ids', [])
                            item['related_full_sources'] = []
                            for rid in related_id_list:
                                if isinstance(rid, int) and 0 <= rid < len(news_items) and rid != main_id:
                                    related_item = news_items[rid]
                                    # Extra guard: only keep when titles strongly match
                                    if AIProcessor._looks_like_same_event(item, related_item):
                                        item['related_full_sources'].append({
                                            'source': related_item['source'],
                                            'title': related_item['title'],
                                            'link': related_item['link']
                                        })
                                    
                            final_result[canonical_category].append(item)
            
            # Sort each category by priority_score (Descending)
            for category in final_result:
                final_result[category].sort(key=lambda x: x.get('priority_score', 0), reverse=True)
                            
            return final_result

        except Exception as e:
            print(f"Error in AI Processing: {e}")
            try:
                if 'response' in locals() and hasattr(response, 'text'):
                    print(f"Response snippet: {response.text[:200]}...")
            except:
                pass
            return {}

    def filter_important_titles(self, news_items, top_k=30):
        """
        Ranks news items by importance and returns indices of top_k items.
        Used by older versions of main.py.
        """
        if not news_items: return []
        
        titles = [f"{i}: {item['title']}" for i, item in enumerate(news_items)]
        prompt = f"다음 뉴스 제목들 중 가장 중요하고 영향력 있는 {top_k}개를 골라 번호만 JSON 배열로 응답하세요.\n" + "\n".join(titles)
        
        try:
            response = self.client.models.generate_content(
                model=config.model_flash,
                contents=prompt,
                config={'response_mime_type': 'application/json'}
            )
            indices = json.loads(response.text)
            return [int(i) for i in indices if isinstance(i, (int, str)) and str(i).isdigit() and int(i) < len(news_items)]
        except:
            return list(range(min(len(news_items), top_k)))

    def process_international_news(self, news_items):
        """Categorize and filter international news."""
        return self.process_domestic_news(news_items) # Reuse logic

    def generate_briefing(self, categorized_news):
        """
        Generates a briefing summary and sentiment analysis (Good/Bad news).
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
        You are a financial news analyst. Based on the categorization of today's news, provide a briefing.

        CRITICAL RULE: 
        1. ALL OUTPUTS MUST BE IN KOREAN (한국어로 작성하세요).
        2. You MUST search thoroughly for BOTH "Bullish/Good News" (Hojae) and "Bearish/Bad News" (Akjae). Do not ignore negative news.

        Task:
        1. **Section Summary**: Write ONE concise sentence summarizing the key trend for each section.
        2. **Company Sentiment**: Identify as many companies as possible affected by Hojae or Akjae.
           - Search specifically for negative news (earnings shock, investigations, strikes, debt, etc.) to fill the 'akjae' list.
           - Provide a very short reason (under 10 characters) for each.
           - Format: "회사명: 이유"
        
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
            print(f"Error generating briefing: {e}")
            return None

if __name__ == "__main__":
    # Dummy test
    processor = AIProcessor()
    # result = processor.process_domestic_news([...])
    pass
