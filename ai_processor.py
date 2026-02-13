from google import genai
import json
import re
import os
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
        당신은 모닝뉴스봇의 전문 뉴스 분류기입니다. Gemini 3 Flash의 향상된 문맥 파악 능력을 활용해 아래 규칙대로 처리하세요.

        1단계: 필터링 (포용적)
        - ❌ 제외: 연예/가십, 단순 영화 홍보, 경기 스코어만 나열된 스포츠
        - ✅ 포함: 비즈니스·정책·경제·산업·기업·금융·과학기술 관련 뉴스 전체
        - 의심스러울 때는 독자에게 정보를 제공한다는 측면에서 포함(KEEP)합니다.

        2단계: 카테고리 분류 및 테마 지정
        - 정치: 정부, 정당, 외교, 입법. (정상/외교, 당내 정국, 사법/의혹, 지방/행정, 입법/정책, Science/Tech 중 택1)
          ·각 테마별 가장 상징적인 기사는 'is_representative=true'로 설정하고 맨 앞에 배치하세요.
        - 경제/거시: 거시경제, 금리, 물가, 금융시장 지표.
        - 기업/산업: 특정 기업 소식 및 산업 동향. (반도체, 자동차, AI/로봇 등 지정된 섹터 필수 입력)
        - 부동산: 정책, 분양, 건설 시장 흐름.
        - 국제: 해외 현지 뉴스 및 글로벌 관계.

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

        정치 기사 테마 분류 (5~7개 테마로 분류):
        - 정상/외교: 대통령 행보, 국제 관계, 북한 동향, 외교 정책
        - 당내 정국: 정당 내부 갈등, 인사, 선거 준비, 지도부 교체
        - 사법/의혹: 수사, 재판, 각종 의혹 및 논란, 공천 비리
        - 지방/행정: 지역 사회 이슈, 행정 통합, 지자체 소식
        - 입법/정책: 법안 발의, 정부 정책 발표, 복지, 규제
        - Science/Tech: IT, AI, 과학 기술 관련 정책 (정치 섹션 내 별도 분류)
        
        정치 기사 처리 규칙:
        1) 각 테마별로 가장 중요도가 높거나 상징적인 기사를 대표 기사(is_representative=true)로 선정
        2) 동일한 사건을 다룬 여러 기사는 하나로 묶어 related_article_ids에 추가
        3) 대표 기사는 각 테마의 맨 앞에 배치됨

        3단계: 지능형 중복 병합 (Reasoning 활용)
        - 단순히 키워드가 겹치는 것이 아니라, "동일 주체, 동일 사건, 동일 시점"인지 내부적으로 먼저 추론한 뒤 병합하세요.
        - 대표 기사 ID를 중심으로 관련된 기사 ID들을 'related_article_ids' 리스트에 엄격하게 묶으세요.

        출력(JSON):
        {{
            "정치": [
                {{"id": 0, "pol_subcategory": "정상/외교", "is_representative": true, "related_article_ids": [1, 2]}},
                {{"id": 5, "pol_subcategory": "입법/정책", "is_representative": false, "related_article_ids": []}}
            ],
            "경제/거시": [...],
            "기업/산업": [
                {{"id": 10, "sector": "반도체", "related_article_ids": [11]}},
                {{"id": 15, "sector": "자동차", "related_article_ids": []}}
            ],
            "부동산": [...],
            "국제": [...]
        }}

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
                                item['is_representative'] = group.get('is_representative', False)

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

    @staticmethod
    def _load_current_leaders():
        """Load current leader anchors from file if present, otherwise fallback defaults."""
        defaults = {
            "한국 대통령": "이재명",
            "미국 대통령": "트럼프",
            "중국 국가주석": "시진핑",
            "러시아 대통령": "푸틴",
            "일본 총리": "다카이치 사나에",
        }

        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            path = os.path.join(base_dir, "data_cache", "current_leaders.json")
            if not os.path.exists(path):
                return defaults

            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)

            if isinstance(payload, dict):
                data = payload.get("data", payload)
                if isinstance(data, dict):
                    merged = {**defaults}
                    for k, v in data.items():
                        if isinstance(k, str) and isinstance(v, str) and k.strip() and v.strip():
                            merged[k.strip()] = v.strip()
                    return merged
        except Exception as e:
            print(f"⚠️ current_leaders 로드 실패(기본값 사용): {e}")

        return defaults

    @staticmethod
    def _normalize_person_name(name: str, role: str, leaders: dict[str, str]) -> str:
        n = (name or "").strip()
        r = (role or "").strip()
        if not n:
            return n

        # 한자/약칭 보정: 대통령 직책 문맥의 李 계열은 현재 한국 대통령으로 정규화
        if "대통령" in r and n in {"李", "李대통령", "이 대통령", "이대통령"}:
            return leaders.get("한국 대통령", n)

        # 역할 포함 이름 정리: "트럼프 대통령" -> "트럼프"
        n = re.sub(r"\s*(대통령|총리|국가주석|위원장|장관)$", "", n).strip()
        return n

    @staticmethod
    def _normalize_person_role(role: str) -> str:
        r = re.sub(r"\s+", " ", (role or "")).strip()
        # 과도한 접두 제거(보수적): "現 "만 제거, "전"은 문맥상 의미가 있어 유지
        r = re.sub(r"^現\s*", "", r)
        return r

    def generate_briefing(self, categorized_news):
        """
        DEPRECATED: Use SentimentAnalyzer.analyze_sentiment() instead.
        This method is kept for backward compatibility but should not be used.
        """
        print("⚠️ WARNING: AIProcessor.generate_briefing() is deprecated. Use SentimentAnalyzer.analyze_sentiment() instead.")
        from sentiment_analyzer import SentimentAnalyzer
        sentiment = SentimentAnalyzer()
        return sentiment.analyze_sentiment(categorized_news)

    def extract_key_persons(self, categorized_news):
        """
        Extract key persons from news articles and group articles by person.
        Returns a dict mapping person names to their related articles.
        """
        if not categorized_news:
            return {}
        
        # Prepare context with article IDs
        articles_list = []
        article_map = {}
        idx = 0
        
        for category, items in categorized_news.items():
            for item in items:
                article_info = {
                    'id': idx,
                    'title': item['title'],
                    'category': category,
                    'source': item['source'],
                    'link': item['link'],
                    'published_dt': item['published_dt'],
                    'original_item': item
                }
                articles_list.append(article_info)
                article_map[idx] = article_info
                idx += 1
        
        if not articles_list:
            return {}
        
        # Create context for AI
        context = "\n".join([f"ID:{a['id']} | {a['category']} | {a['title']}" for a in articles_list])
        current_leaders = self._load_current_leaders()
        leader_anchor_lines = [f"- {role}: {name}" for role, name in current_leaders.items()]
        leader_anchor_text = "\n".join(leader_anchor_lines)
        
        prompt = f"""
        당신은 뉴스 분석 전문가입니다. 다음 뉴스 기사들에서 자주 등장하는 주요 인물을 찾아주세요.

        규칙:
        1. 3개 이상의 기사에서 언급되는 인물만 추출
        2. 정치인, 기업인, 국제 인물 등 모든 중요 인물 포함
        3. 각 인물과 관련된 기사 ID를 모두 나열
        4. 인물명은 정확하게 표기 (예: "이혜훈", "마두로")
        5. 5개 이상의 기사와 관련된 인물을 우선적으로 추출
        6. role은 현재 직책/역할을 최대한 정확하게 표기 (예: "한국 대통령", "미국 대통령", "중국 국가주석")
           - "전 대통령", "前 대통령" 같은 과거 직책 표기는 최소화
           - 뉴스에서 현재 활동 중이면 현재 역할로 표기
        7. 아래 "현재 지도자 기준"을 우선 참조하세요.

        현재 지도자 기준:
        {leader_anchor_text}

        출력 JSON 형식:
        {{
            "key_persons": [
                {{
                    "name": "인물명",
                    "article_ids": [1, 5, 10, 15],
                    "count": 4,
                    "role": "현재 직책 또는 역할 (예: 국민의힘 대선후보, 베네수엘라 대통령)"
                }}
            ]
        }}
        
        입력 뉴스:
        {context}
        """
        
        try:
            response = self.client.models.generate_content(
                model=config.model_flash,
                contents=prompt,
                config={'response_mime_type': 'application/json'}
            )
            
            result = json.loads(response.text)
            persons_data = {}
            
            # Process each person
            for person_info in result.get('key_persons', []):
                raw_name = person_info.get('name')
                article_ids = person_info.get('article_ids', [])
                role = self._normalize_person_role(person_info.get('role', ''))
                name = self._normalize_person_name(raw_name, role, current_leaders)
                
                # Filter: only keep persons with 3+ articles
                if not name:
                    continue

                # article_ids 정합성 보정 및 중복 제거
                valid_ids = []
                seen_ids = set()
                if isinstance(article_ids, list):
                    for aid in article_ids:
                        if isinstance(aid, int) and aid in article_map and aid not in seen_ids:
                            seen_ids.add(aid)
                            valid_ids.append(aid)
                
                # Collect actual articles
                related_articles = []
                for aid in valid_ids:
                    related_articles.append(article_map[aid]['original_item'])

                # LLM count 신뢰 대신 실제 기사 수로 재계산
                count = len(related_articles)
                
                if len(related_articles) >= 3:
                    # 역할 비어있으면 현재 지도자 앵커에서 보강
                    if not role:
                        for leader_role, leader_name in current_leaders.items():
                            if leader_name == name:
                                role = leader_role
                                break
                    persons_data[name] = {
                        'articles': related_articles,
                        'count': count,
                        'role': role
                    }
            
            # Sort by article count (descending)
            persons_data = dict(sorted(persons_data.items(), key=lambda x: x[1]['count'], reverse=True))
            
            return persons_data
            
        except Exception as e:
            print(f"Error extracting key persons: {e}")
            # Important: return None on failure so callers can avoid overwriting caches.
            return None

if __name__ == "__main__":
    # Dummy test
    processor = AIProcessor()
    # result = processor.process_domestic_news([...])
    pass
