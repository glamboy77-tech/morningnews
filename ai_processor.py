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
        You are a news editor. Your task has THREE STEPS:
        
        **STEP 1: FILTER** - Include most articles, remove only truly irrelevant ones:
        - ❌ REMOVE ONLY: Unrelated entertainment (celebrity gossip, movies), pure sports scores, viral social trends
        - ✅ KEEP: All business news, policy news, economic news, industry news, company announcements, market reports
        - ✅ KEEP: All news about economics, politics, companies, real estate, international affairs
        - ⚠️ INCLUSIVE APPROACH: When in doubt, KEEP the article. Better to show more relevant news than too little.
        
        **STEP 2: CATEGORIZE** remaining articles into ONE of these sections:
        - Politics (정치): Government, politicians, political parties, elections, legislation
        - Economy/Macro (경제/거시): Economic policy, GDP, inflation, unemployment, fiscal/monetary policy, financial markets
        - Corporate/Industry (기업/산업): Specific companies, industries, business deals, corporate earnings
        - Real Estate (부동산): Housing, property market, construction, real estate policy
        - International (국제): Foreign news, international relations, global events
        
        **STEP 3: DEDUPLICATE** within each category using VERY STRICT criteria.
        
        ⚠️ CRITICAL DEDUPLICATION RULES:
        
        Articles are duplicates ONLY if ALL THREE conditions are met:
        1. **Same Entity**: Same person, same company, same organization, or same specific event
        2. **Same Event**: Same announcement, same incident, same development (not just similar topic)
        3. **Same Timeframe**: Same day or same specific occurrence
        
        ❌ **DO NOT GROUP** these cases (they are NOT duplicates):
        - Different companies in same industry (e.g., "Samsung earnings" ≠ "LG earnings")
        - Different politicians in same party (e.g., "Person A statement" ≠ "Person B statement")
        - Different regions/cities (e.g., "Seoul housing" ≠ "Busan housing")
        - Different countries (e.g., "US economy" ≠ "China economy")
        - Different events on same topic (e.g., "Stock market rises" ≠ "Dollar strengthens")
        - Different aspects of same issue (e.g., "Policy announced" ≠ "Opposition reaction")
        
        ✅ **DO GROUP** these cases (they ARE duplicates):
        - Same event from different news sources (e.g., multiple outlets reporting "Samsung announces Q4 earnings")
        - Same speech/announcement reported by different media
        - Same incident with different headlines but identical core event
        
        **When in doubt, keep them SEPARATE**. It's better to show distinct news separately than to incorrectly merge different events.
        
        **IMPORTANT**: Only return articles that pass Step 1 filter (important hard news). Low-quality content should be completely excluded from the output.
        
        Output Format (MUST be valid JSON):
        {{
            "정치": [
                {{"id": 0, "related_article_ids": [1, 2]}},
                {{"id": 5, "related_article_ids": []}}
            ],
            "경제/거시": [...],
            "기업/산업": [...],
            "부동산": [...],
            "국제": [...]
        }}
        
        - "id": The ID of the MOST representative article among duplicates
        - "related_article_ids": IDs of other articles covering the EXACT SAME EVENT (usually empty or 1-3 IDs max)
        
        Input News:
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
