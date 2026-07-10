import feedparser
import re
import html
from urllib.parse import parse_qs, quote_plus, urlparse
from datetime import datetime
from config import config


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


NOISE_TITLE_PATTERNS = [
    r"^\s*\[포토\]",
    r"^\s*\[사진\]",
    r"^\s*\[화보\]",
    r"^\s*\[영상\]",
    r"^\s*\[게시판\]",
    r"^\s*\[인사\]",
    r"^\s*\[부고\]",
    r"^\s*\[오늘의 운세\]",
    r"올스타전",
    r"퓨처스 올스타",
    r"\bKIA\b.*(투수|타자|캐치|하트|돌직구|역투)",
    r"\bNC\b.*(투수|타자|역투)",
    r"\b롯데\b.*(투수|타자|역투)",
    r"\b한화\b.*(투수|타자|역투|독수리)",
    r"매니저 갑질",
    r"층간소음 논란",
    r"포워드 가이던스 시대의 종말",
]

NOISE_SOURCE_SUFFIXES = [
    "Vietnam.vn",
]


def build_google_news_rss(query: str) -> str:
    """Build a Korean Google News RSS search URL for keyword/official-source coverage."""
    return f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=ko&gl=KR&ceid=KR:ko"


def is_noise_article(title: str, description: str = "", *, source_type: str = "rss") -> bool:
    """Filter obvious non-briefing noise before expensive LLM categorization."""
    text = html.unescape(f"{title or ''} {description or ''}")
    for pattern in NOISE_TITLE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True

    if source_type == "google_keyword":
        # Keyword feeds are only auxiliary; drop obvious foreign aggregator hits.
        if any(suffix in (title or "") for suffix in NOISE_SOURCE_SUFFIXES):
            return True

    # Require at least some Korean text for Korean morning briefing sources.
    if not re.search(r"[가-힣]", title or ""):
        return True

    return False


def infer_source_type(source_name: str, url: str = "") -> str:
    name = source_name or ""
    lower_url = (url or "").lower()
    if name.startswith("공식-") or any(token in name for token in ["한국은행", "금융위원회", "국토교통부", "기획재정부", "산업통상자원부", "통계청", "공정거래위원회", "서울시", "경기도"]):
        return "official"
    if name.startswith("테크-") or any(token in name for token in ["ZDNet", "전자신문", "디지털데일리", "AI타임스", "블로터", "TechCrunch", "The Verge"]):
        return "tech"
    if "사이언스타임즈" in name:
        return "tech"
    if name.startswith("키워드-") or "news.google.com/rss/search" in lower_url:
        return "google_keyword"
    if name.startswith("부동산-") or "부동산" in name or "건설" in name:
        return "realestate"
    if any(token in name for token in ["연합뉴스", "뉴스1", "뉴시스"]):
        return "wire"
    if any(token in name for token in ["한국경제", "매일경제", "서울경제", "머니투데이", "이데일리", "조선비즈", "비즈워치", "아시아경제"]):
        return "economy"
    return "rss"


def enrich_news_item(item: dict, *, source_type: str | None = None) -> dict:
    """Attach normalized source metadata used by ranking and HTML badges."""
    inferred = source_type or item.get("source_type") or infer_source_type(item.get("source", ""), item.get("feed_url", "") or item.get("link", ""))
    meta = SOURCE_TYPE_META.get(inferred, SOURCE_TYPE_META["rss"])
    item["source_type"] = inferred
    item["source_weight"] = float(item.get("source_weight") or meta["weight"])
    item["source_badge"] = item.get("source_badge") or meta["badge"]
    return item


def normalize_title_for_dedupe(title: str) -> str:
    title = html.unescape(title or "")
    title = re.sub(r"\s+-\s+[^-]{2,30}$", "", title)
    title = re.sub(r"\[[^\]]+\]", "", title)
    title = re.sub(r"[^0-9A-Za-z가-힣\s]", " ", title)
    return re.sub(r"\s+", " ", title).strip().lower()


def canonical_link_for_dedupe(link: str) -> str:
    link = html.unescape(link or "").strip()
    if not link:
        return ""
    parsed = urlparse(link)
    # Google News RSS sometimes wraps original URLs in url= query params.
    qs = parse_qs(parsed.query)
    for key in ("url", "u"):
        if qs.get(key):
            return qs[key][0]
    return f"{parsed.netloc}{parsed.path}".rstrip("/").lower()


def deduplicate_news_items(items: list[dict]) -> list[dict]:
    """Conservative URL/title dedupe while preserving higher-weight representative items."""
    best_by_key: dict[str, dict] = {}
    dropped = 0
    for raw in items:
        if not isinstance(raw, dict):
            continue
        item = enrich_news_item(raw)
        link_key = canonical_link_for_dedupe(item.get("link", ""))
        title_key = normalize_title_for_dedupe(item.get("title", ""))
        key = link_key or title_key
        if not key:
            continue

        existing = best_by_key.get(key)
        if not existing:
            best_by_key[key] = item
            continue

        dropped += 1
        existing_related = existing.setdefault("deduped_sources", [])
        existing_related.append({
            "source": item.get("source", ""),
            "title": item.get("title", ""),
            "link": item.get("link", ""),
        })

        existing_score = float(existing.get("source_weight", 1.0))
        item_score = float(item.get("source_weight", 1.0))
        if item_score > existing_score:
            item.setdefault("deduped_sources", []).extend(existing_related)
            item["deduped_sources"].append({
                "source": existing.get("source", ""),
                "title": existing.get("title", ""),
                "link": existing.get("link", ""),
            })
            best_by_key[key] = item

    result = list(best_by_key.values())
    result.sort(key=lambda x: (x.get("published_dt") or datetime.min), reverse=True)
    if dropped:
        print(f"  - Dedupe removed/merged {dropped} duplicate RSS items")
    return result

class RSSManager:
    def __init__(self):
        self.config = config

    @staticmethod
    def _entry_limit_for_source(source_type: str) -> int:
        if source_type == "google_keyword":
            return 15
        if source_type == "official":
            return 30
        if source_type in {"wire", "economy"}:
            return 50
        return 40

    def fetch_feeds(self):
        """
        Fetches all feeds and returns a list of dictionaries.
        Each item has: title, link, source, published, published_struct, description
        """
        all_news = []

        # 1. Domestic Feeds
        print("Fetching Domestic Feeds...")
        for source_name, url in self.config.domestic_feeds.items():
            try:
                feed = feedparser.parse(url)
                print(f"  - {source_name}: {len(feed.entries)} entries found.")
                source_type = infer_source_type(source_name, url)
                
                entries = feed.entries[: self._entry_limit_for_source(source_type)]
                for entry in entries:
                    # Parse date
                    published = entry.get('published_parsed') or entry.get('updated_parsed')
                    if not published:
                        continue
                        
                    import calendar
                    from datetime import timezone, timedelta
                    
                    # feedparser.published_parsed is in UTC
                    utc_secs = calendar.timegm(published)
                    pub_dt = datetime.fromtimestamp(utc_secs, tz=timezone.utc).astimezone(timezone(timedelta(hours=9)))
                    # Strip timezone info for legacy code compatibility if needed, or keep for accuracy
                    pub_dt = pub_dt.replace(tzinfo=None)
                    
                    # Store all articles, we will filter/limit later in main.py
                    title = entry.get('title', 'No Title')
                    description = entry.get('description', '')
                    if is_noise_article(title, description, source_type=source_type):
                        continue

                    item = {
                        'title': title,
                        'link': entry.get('link', ''),
                        'source': source_name,
                        'published_dt': pub_dt,
                        'description': description,
                        'category': 'domestic',
                        'feed_url': url,
                    }
                    all_news.append(enrich_news_item(item, source_type=source_type))
            except Exception as e:
                print(f"Error fetching {source_name}: {e}")

        return deduplicate_news_items(all_news)

if __name__ == "__main__":
    manager = RSSManager()
    news = manager.fetch_feeds()
    print(f"Total entries fetched: {len(news)}")
    for item in news[:5]:
        print(f"[{item['source']}] {item['title']} ({item['published_dt']})")
