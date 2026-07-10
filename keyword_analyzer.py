import re
from collections import defaultdict


class KeywordAnalyzer:
    """Local, deterministic keyword ranking for daily news.

    LLM을 쓰지 않고 제목/설명 반복 출현, 기사 수, 출처 다양성, 카테고리 다양성을
    점수화해 포털 키워드 랭킹처럼 TOP 키워드를 만든다.
    """

    STOPWORDS = {
        "오늘", "뉴스", "기사", "단독", "종합", "속보", "영상", "사진", "포토", "화보",
        "관련", "이번", "지난", "내년", "올해", "최근", "오전", "오후", "기자", "보도",
        "정부", "시장", "업계", "기업", "국내", "한국", "미국", "중국", "일본", "서울",
        "전국", "지역", "억원", "만원", "원대", "퍼센트", "상승", "하락", "확대", "추진",
        "발표", "공개", "논의", "대응", "지원", "강화", "개최", "참석", "시작", "종료",
        "따르면", "밝혔다", "밝힌", "밝혀", "있다", "있는", "했다", "한다", "됐다", "된다",
        "위해", "위한", "통해", "대한", "대해", "두고", "앞서", "이어", "가운데", "현지", "온라인",
        "시간", "이날", "것으로", "것은", "것이", "것을", "있는", "없는", "보다", "면서", "까지",
        "대상", "경우", "이후", "이전", "다시", "처음", "최대", "최소", "전체", "일부",
        "글로벌", "서비스", "전환", "출시", "운영", "개선", "활용", "기반", "확인",
        "가장", "추가", "도입", "완료", "재개", "선정", "주요", "핵심", "이상", "이하",
        "중심", "속도", "대폭", "연속", "사실", "역대", "모두", "동시", "대비", "유지",
        "가능성", "전망", "분석", "계획", "상황", "문제", "이슈", "사태", "관계", "정책",
        "대통령", "대표", "위원장", "장관", "후보", "의원", "총리", "회장", "부회장",
        "연합뉴스", "조선일보", "동아일보", "매일경제", "한국경제", "서울경제", "이데일리",
        "전자신문", "ZDNetKorea", "ZDNet", "사이언스타임즈", "땅집고", "머니투데이", "블로터",
        "뉴스1", "뉴시스", "로이터", "AP", "AFP", "CNN", "BBC", "nbsp", "amp",
        "사용자메뉴", "과학기술", "과학문화", "생명과학", "의학", "정보통신기술",
        "뉴스레터", "메뉴", "홈페이지", "사이트", "바로가기",
    }

    # 뉴스에서 의미 있는 복합 이슈어는 형태소 분석 없이도 잡히도록 별도 사전으로 보강한다.
    HOT_PHRASES = [
        "AI 반도체", "인공지능", "반도체", "메모리", "HBM", "엔비디아", "삼성전자", "SK하이닉스",
        "기준금리", "금리", "환율", "코스피", "코스닥", "주식시장", "자사주", "배당", "ETF",
        "부동산 대책", "대출 규제", "주택 공급", "전세", "재건축", "분양", "청약", "집값",
        "전기차", "2차전지", "배터리", "자동차", "조선", "방산", "원전", "바이오", "제약",
        "관세", "공급망", "유가", "물가", "소비", "수출", "수입", "무역", "재정", "추경",
        "금융위", "금융감독원", "한국은행", "국토교통부", "공정거래위원회", "기획재정부",
        "북한", "우크라이나", "러시아", "이스라엘", "중동", "트럼프", "연준", "FOMC",
    ]

    # 너무 흔한 회사/기관 접미 표현을 정리할 때 사용한다.
    TRAILING_PARTICLES = "은는이가을를의에와과도만로으로에서부터까지보다"

    def __init__(self):
        self._phrase_patterns = [
            (phrase, re.compile(re.escape(phrase).replace("\\ ", r"\s*"), re.IGNORECASE))
            for phrase in self.HOT_PHRASES
        ]

    @staticmethod
    def _plain_text(value) -> str:
        text = str(value or "")
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"&[a-zA-Z]+;", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    @classmethod
    def _normalize_keyword(cls, token: str) -> str:
        token = (token or "").strip("'\"“”‘’()[]{}<>.,!?…·:;|/\\")
        token = re.sub(r"\s+", " ", token)
        if len(token) > 3:
            token = token.rstrip(cls.TRAILING_PARTICLES)
        aliases = {
            "에이아이": "AI",
            "인공지능": "AI",
            "미연준": "연준",
            "美연준": "연준",
            "오픈AI": "OpenAI",
            "오픈ai": "OpenAI",
            "에스케이하이닉스": "SK하이닉스",
        }
        return aliases.get(token, token)

    @classmethod
    def _is_valid_keyword(cls, token: str) -> bool:
        if not token:
            return False
        if token in cls.STOPWORDS:
            return False
        if len(token) < 2 or len(token) > 16:
            return False
        if token.isdigit():
            return False
        if re.fullmatch(r"\d+[년월일시분초%℃달러원조억만개명건배선위]+", token):
            return False
        if re.fullmatch(r"[가-힣]{1,2}(?:씨|님|군|양)", token):
            return False
        return True

    def _extract_candidates(self, text: str):
        candidates = []
        clean = self._plain_text(text)
        if not clean:
            return candidates

        # 복합 이슈어 우선 추출
        for phrase, pattern in self._phrase_patterns:
            if pattern.search(clean):
                candidates.append(phrase)

        # 한글/영문/숫자 혼합 토큰 추출: AI, HBM, 2차전지, 코스피 등
        raw_tokens = re.findall(r"[A-Za-z]{2,12}|[A-Za-z0-9가-힣]{2,16}|[가-힣]{2,12}", clean)
        for token in raw_tokens:
            normalized = self._normalize_keyword(token)
            if self._is_valid_keyword(normalized):
                candidates.append(normalized)

        return candidates

    @staticmethod
    def _iter_articles(categorized_news, science_news=None):
        if isinstance(categorized_news, dict):
            for category, items in categorized_news.items():
                if not isinstance(items, list):
                    continue
                for item in items:
                    if isinstance(item, dict):
                        yield category, item
        if isinstance(science_news, list):
            for item in science_news:
                if isinstance(item, dict):
                    yield "테크", item

    def extract_top_keywords(self, categorized_news, science_news=None, *, limit: int = 10):
        stats = defaultdict(lambda: {
            "title_hits": 0,
            "description_hits": 0,
            "article_links": set(),
            "sources": set(),
            "categories": set(),
            "sample_titles": [],
        })

        for category, item in self._iter_articles(categorized_news, science_news):
            title = self._plain_text(item.get("title", ""))
            description = self._plain_text(item.get("description", ""))[:350]
            link = item.get("link") or f"{item.get('source', '')}:{title}"
            source = item.get("source", "") or "unknown"

            title_candidates = set(self._extract_candidates(title))
            desc_candidates = set(self._extract_candidates(description))
            all_candidates = title_candidates | desc_candidates

            for keyword in all_candidates:
                data = stats[keyword]
                if keyword in title_candidates:
                    data["title_hits"] += 1
                if keyword in desc_candidates:
                    data["description_hits"] += 1
                data["article_links"].add(link)
                data["sources"].add(source)
                data["categories"].add(category)
                if title and len(data["sample_titles"]) < 3:
                    data["sample_titles"].append(title)

        ranked = []
        for keyword, data in stats.items():
            article_count = len(data["article_links"])
            source_count = len(data["sources"])
            category_count = len(data["categories"])

            # 최소 2개 기사 이상 + 제목 반복 1회 이상이어야 랭킹 후보로 인정
            if article_count < 2 or data["title_hits"] < 1:
                continue

            score = (
                data["title_hits"] * 3.0
                + data["description_hits"] * 0.8
                + article_count * 2.0
                + source_count * 0.9
                + category_count * 1.2
            )
            ranked.append({
                "keyword": keyword,
                "score": round(score, 2),
                "article_count": article_count,
                "source_count": source_count,
                "categories": sorted(data["categories"]),
                "sample_titles": data["sample_titles"],
            })

        ranked.sort(key=lambda x: (x["score"], x["article_count"], x["source_count"]), reverse=True)
        top = ranked[:limit]
        for idx, item in enumerate(top, start=1):
            item["rank"] = idx
        return top