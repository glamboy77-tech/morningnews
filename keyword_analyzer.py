import re
from collections import defaultdict


class KeywordAnalyzer:
    """Hybrid keyword ranking for daily news.

    브리핑 LLM이 뽑은 후보가 있으면 그 후보를 우선 검증/카운트하고,
    부족한 경우 로컬 빈도 기반 후보로 보충한다. 별도 LLM 호출은 하지 않는다.
    """

    STOPWORDS = {
        "오늘", "뉴스", "기사", "단독", "종합", "속보", "영상", "사진", "포토", "화보",
        "관련", "이번", "지난", "내년", "올해", "최근", "오전", "오후", "기자", "보도",
        "정부", "시장", "업계", "기업", "국내", "한국", "미국", "중국", "일본", "서울",
        "전국", "지역", "억원", "만원", "원대", "퍼센트", "상승", "하락", "확대", "추진",
        "발표", "공개", "논의", "대응", "지원", "강화", "개최", "참석", "시작", "종료",
        "따르면", "밝혔다", "밝힌", "밝혀", "있다", "있는", "했다", "한다", "됐다", "된다",
        "위해", "위한", "통해", "대한", "대해", "두고", "앞서", "이어", "가운데", "현지", "온라인",
        "시간", "이날", "것으로", "것은", "것이", "것을", "있는", "없는", "보다", "면서", "까지", "만에",
        "대상", "경우", "이후", "이전", "다시", "처음", "최대", "최소", "전체", "일부",
        "글로벌", "서비스", "전환", "출시", "운영", "개선", "활용", "기반", "확인",
        "가장", "추가", "도입", "완료", "재개", "선정", "주요", "핵심", "이상", "이하",
        "중심", "속도", "대폭", "연속", "사실", "역대", "모두", "동시", "대비", "유지",
        "본격화", "급등", "급락", "급증", "감소", "증가", "돌파", "부각", "확산", "회복",
        "가능성", "전망", "분석", "계획", "상황", "문제", "이슈", "사태", "관계", "정책",
        "사업", "중구", "동구", "서구", "남구", "북구", "강남", "강북", "도심", "지방",
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

    # 너무 흔한 조사 접미 표현을 정리할 때 사용한다. rstrip(char set)을 쓰면
    # "레버리지" 같은 정상 단어가 "레버리"로 잘릴 수 있어 suffix 단위로만 제거한다.
    TRAILING_PARTICLES = ("으로", "에서", "부터", "까지", "보다", "은", "는", "이", "가", "을", "를", "의", "에", "와", "과", "도", "만", "로")

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
            for suffix in cls.TRAILING_PARTICLES:
                if token.endswith(suffix) and len(token) - len(suffix) >= 2:
                    token = token[:-len(suffix)]
                    break
        aliases = {
            "에이아이": "AI",
            "인공지능": "AI",
            "미연준": "연준",
            "美연준": "연준",
            "오픈AI": "OpenAI",
            "오픈ai": "OpenAI",
            "에스케이하이닉스": "SK하이닉스",
            "국힘": "국민의힘",
        }
        return aliases.get(token, token)

    @staticmethod
    def _person_names_from_key_persons(key_persons) -> set[str]:
        if not isinstance(key_persons, dict):
            return set()
        return {str(name).strip() for name in key_persons.keys() if str(name).strip()}

    @classmethod
    def _normalize_llm_candidate(cls, candidate):
        if isinstance(candidate, str):
            keyword = candidate
        elif isinstance(candidate, dict):
            keyword = candidate.get("keyword") or candidate.get("name") or candidate.get("term")
        else:
            return None

        normalized = cls._normalize_keyword(str(keyword or ""))
        if not cls._is_valid_keyword(normalized):
            return None
        return normalized

    @classmethod
    def _normalize_llm_candidate_detail(cls, candidate):
        """LLM 키워드 후보를 화면 표시/기사 매칭에 쓸 수 있는 형태로 보존한다."""
        keyword = cls._normalize_llm_candidate(candidate)
        if not keyword:
            return None

        reason = ""
        categories = []
        if isinstance(candidate, dict):
            reason = str(candidate.get("reason") or "").strip()
            raw_categories = candidate.get("categories") or []
            if isinstance(raw_categories, list):
                categories = [str(c).strip() for c in raw_categories if str(c).strip()]
            elif isinstance(raw_categories, str) and raw_categories.strip():
                categories = [raw_categories.strip()]

        return {
            "keyword": keyword,
            "reason": reason,
            "categories": categories,
        }

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

    @classmethod
    def _compact(cls, text: str) -> str:
        return re.sub(r"[^0-9A-Za-z가-힣]+", "", str(text or "")).lower()

    @classmethod
    def _match_terms_for_llm_keyword(cls, keyword: str, reason: str = ""):
        """의미형 LLM 키워드와 reason에서 기사 매칭용 힌트 단어를 느슨하게 만든다."""
        terms = []
        for raw in [keyword, reason]:
            clean = cls._plain_text(raw)
            if not clean:
                continue
            terms.append(clean)
            terms.append(cls._compact(clean))
            for token in re.findall(r"[A-Za-z]{2,12}|[A-Za-z0-9가-힣]{2,16}|[가-힣]{2,12}", clean):
                normalized = cls._normalize_keyword(token)
                if cls._is_valid_keyword(normalized):
                    terms.append(normalized)
                    terms.append(cls._compact(normalized))

        # 너무 짧거나 중복된 힌트 제거. 순서는 보존한다.
        seen = set()
        unique_terms = []
        for term in terms:
            term = str(term or "").strip()
            if len(term) < 2 or term in seen:
                continue
            seen.add(term)
            unique_terms.append(term)
        return unique_terms

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

    def extract_top_keywords(self, categorized_news, science_news=None, *, limit: int = 10, key_persons=None):
        return self._rank_keywords(
            categorized_news,
            science_news,
            limit=limit,
            key_persons=key_persons,
            preferred_keywords=None,
        )

    def extract_hybrid_keywords(
        self,
        categorized_news,
        science_news=None,
        *,
        llm_candidates=None,
        limit: int = 10,
        key_persons=None,
    ):
        preferred_details = []
        seen = set()
        if isinstance(llm_candidates, list):
            for candidate in llm_candidates:
                detail = self._normalize_llm_candidate_detail(candidate)
                if not detail or detail["keyword"] in seen:
                    continue
                preferred_details.append(detail)
                seen.add(detail["keyword"])

        if preferred_details:
            return self._rank_llm_linked_keywords(
                categorized_news,
                science_news,
                limit=limit,
                key_persons=key_persons,
                preferred_details=preferred_details,
            )

        return self._rank_keywords(
            categorized_news,
            science_news,
            limit=limit,
            key_persons=key_persons,
            preferred_keywords=None,
        )

    def _score_article_for_llm_keyword(self, detail, category, item):
        keyword = detail.get("keyword", "")
        reason = detail.get("reason", "")
        preferred_categories = set(detail.get("categories") or [])
        title = self._plain_text(item.get("title", ""))
        description = self._plain_text(item.get("description", ""))[:500]
        title_compact = self._compact(title)
        desc_compact = self._compact(description)
        keyword_compact = self._compact(keyword)
        terms = self._match_terms_for_llm_keyword(keyword, reason)

        score = 0.0
        text_score = 0.0

        if keyword and keyword in title:
            score += 14.0
            text_score += 14.0
        if keyword and keyword in description:
            score += 5.0
            text_score += 5.0
        if keyword_compact and keyword_compact in title_compact:
            score += 12.0
            text_score += 12.0
        if keyword_compact and keyword_compact in desc_compact:
            score += 4.0
            text_score += 4.0

        for term in terms:
            term_compact = self._compact(term)
            if not term_compact or term_compact == keyword_compact:
                continue
            if term in title or term_compact in title_compact:
                score += 2.5
                text_score += 2.5
            elif term in description or term_compact in desc_compact:
                score += 0.9
                text_score += 0.9

        if category in preferred_categories:
            score += 2.0
        if item.get("is_representative"):
            score += 1.0
        try:
            score += min(float(item.get("source_weight") or 0), 1.5) * 0.3
        except Exception:
            pass
        try:
            score += min(float(item.get("priority_score") or 0), 5.0) * 0.15
        except Exception:
            pass

        return score, text_score

    @staticmethod
    def _article_payload(item, *, score=None):
        payload = {
            "title": item.get("title", ""),
            "link": item.get("link", ""),
            "source": item.get("source", ""),
            "published_dt": item.get("published_dt", ""),
        }
        if score is not None:
            payload["match_score"] = round(score, 2)
        return payload

    def _build_llm_keyword_item(self, detail, categorized_news, science_news=None):
        best = None
        article_matches = []
        related_links = set()
        sources = set()
        categories = set(detail.get("categories") or [])
        sample_titles = []

        for category, item in self._iter_articles(categorized_news, science_news):
            score, text_score = self._score_article_for_llm_keyword(detail, category, item)
            link = item.get("link") or f"{item.get('source', '')}:{item.get('title', '')}"
            if text_score >= 2.5:
                related_links.add(link)
                sources.add(item.get("source", "") or "unknown")
                categories.add(category)
                article_matches.append((score, text_score, category, item))
                if item.get("title") and len(sample_titles) < 3:
                    sample_titles.append(item.get("title"))

            if score <= 0:
                continue
            if best is None or score > best[0]:
                best = (score, text_score, category, item)

        representative_article = None
        score = 0.0
        if best and (best[1] > 0 or best[2] in set(detail.get("categories") or [])):
            score = best[0]
            representative_article = self._article_payload(best[3], score=best[0])
            categories.add(best[2])
            if best[3].get("source"):
                sources.add(best[3].get("source"))
            if best[3].get("link"):
                related_links.add(best[3].get("link"))
            article_matches.append(best)
            if best[3].get("title") and best[3].get("title") not in sample_titles and len(sample_titles) < 3:
                sample_titles.append(best[3].get("title"))

        related_articles = []
        seen_article_links = set()
        for match_score, text_score, category, item in sorted(article_matches, key=lambda x: x[0], reverse=True):
            link = item.get("link") or f"{item.get('source', '')}:{item.get('title', '')}"
            if not link or link in seen_article_links:
                continue
            seen_article_links.add(link)
            related_articles.append(self._article_payload(item, score=match_score))
            if len(related_articles) >= 5:
                break

        return {
            "keyword": detail.get("keyword", ""),
            "reason": detail.get("reason", ""),
            "score": round(score, 2),
            "article_count": len(related_links),
            "source_count": len(sources),
            "categories": sorted(categories),
            "sample_titles": sample_titles,
            "representative_article": representative_article,
            "related_articles": related_articles,
            "llm_candidate": True,
        }

    @staticmethod
    def _is_near_duplicate_keyword(keyword: str, existing_keywords: set[str]) -> bool:
        compact = re.sub(r"[^0-9A-Za-z가-힣]+", "", str(keyword or "")).lower()
        if not compact:
            return True
        for existing in existing_keywords:
            existing_compact = re.sub(r"[^0-9A-Za-z가-힣]+", "", str(existing or "")).lower()
            if compact == existing_compact:
                return True
            if len(compact) >= 2 and compact in existing_compact:
                return True
            if len(existing_compact) >= 2 and existing_compact in compact:
                return True
        return False

    def _rank_llm_linked_keywords(self, categorized_news, science_news=None, *, limit: int = 10, key_persons=None, preferred_details=None):
        excluded_person_names = self._person_names_from_key_persons(key_persons)
        result = []
        existing_keywords = set()

        for detail in preferred_details or []:
            keyword = detail.get("keyword")
            if not keyword or keyword in excluded_person_names:
                continue
            if self._is_near_duplicate_keyword(keyword, existing_keywords):
                continue
            item = self._build_llm_keyword_item(detail, categorized_news, science_news)
            result.append(item)
            existing_keywords.add(keyword)
            if len(result) >= limit:
                break

        if len(result) < limit:
            local_ranked = self._rank_keywords(
                categorized_news,
                science_news,
                limit=limit * 3,
                key_persons=key_persons,
                preferred_keywords=[d.get("keyword") for d in preferred_details or []],
            )
            for item in local_ranked:
                keyword = item.get("keyword")
                if self._is_near_duplicate_keyword(keyword, existing_keywords):
                    continue
                item["llm_candidate"] = False
                linked = self._build_llm_keyword_item(
                    {
                        "keyword": keyword,
                        "reason": "",
                        "categories": item.get("categories", []),
                    },
                    categorized_news,
                    science_news,
                )
                item["representative_article"] = linked.get("representative_article")
                item["related_articles"] = linked.get("related_articles", [])
                result.append(item)
                existing_keywords.add(keyword)
                if len(result) >= limit:
                    break

        for idx, item in enumerate(result[:limit], start=1):
            item["rank"] = idx
        return result[:limit]

    def _rank_keywords(self, categorized_news, science_news=None, *, limit: int = 10, key_persons=None, preferred_keywords=None):
        excluded_person_names = self._person_names_from_key_persons(key_persons)
        preferred_order = {keyword: idx for idx, keyword in enumerate(preferred_keywords or [])}
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
                if keyword in excluded_person_names:
                    continue
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
            is_llm_candidate = keyword in preferred_order

            score = (
                data["title_hits"] * 3.0
                + data["description_hits"] * 0.8
                + article_count * 2.0
                + source_count * 0.9
                + category_count * 1.2
                + (3.0 if is_llm_candidate else 0.0)
            )
            ranked.append({
                "keyword": keyword,
                "score": round(score, 2),
                "article_count": article_count,
                "source_count": source_count,
                "categories": sorted(data["categories"]),
                "sample_titles": data["sample_titles"],
                "llm_candidate": is_llm_candidate,
            })

        # 사용자가 보는 랭킹은 "많이 언급된 키워드"에 가까워야 하므로 기사 수를 최우선으로 정렬한다.
        # LLM 후보 여부는 동률 근처에서 의미 있는 키워드를 위로 올리는 보조 기준으로만 쓴다.
        ranked.sort(
            key=lambda x: (
                x["article_count"],
                x["source_count"],
                len(x["categories"]),
                1 if x.get("llm_candidate") else 0,
                x["score"],
                -preferred_order.get(x["keyword"], 999),
            ),
            reverse=True,
        )
        top = ranked[:limit]
        for idx, item in enumerate(top, start=1):
            item["rank"] = idx
        return top