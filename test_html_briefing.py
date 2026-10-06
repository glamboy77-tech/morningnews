"""Offline checks for the short daily reading path."""

import tempfile
import unittest
from datetime import datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path

from html_generator import HTMLGenerator


class SectionParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs and attrs.get('class') == 'section-title':
            self.ids.append(attrs['id'])
        if tag == 'a' and attrs.get('class') == 'nav-pill' and attrs.get('href', '').startswith('#'):
            self.links.append(attrs['href'][1:])


class MorningPageTests(unittest.TestCase):
    def test_morning_glance_keeps_sources_but_hides_old_cards(self):
        article = {
            "title": "오늘의 경제 소식",
            "link": "https://example.com/article",
            "source": "테스트뉴스",
            "published_dt": datetime(2026, 10, 5, 6),
        }
        briefing = {
            "section_summaries": {"경제/거시": "오늘의 경제 흐름입니다."},
            "hojae": ["테스트기업: 호재"],
            "akjae": ["테스트기업: 악재"],
        }
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "index.html"
            HTMLGenerator().generate_main_page(
                {"경제/거시": [article]}, [], briefing, {}, str(path), "2026.10.05",
                trending_keywords=[{"keyword": "테스트", "rank": 1}],
            )
            html = path.read_text(encoding="utf-8")
        self.assertIn("오늘의 경제 흐름입니다.", html)
        self.assertIn("Sunday Radar 주간 브리핑", html)
        self.assertIn('<details class="all-articles">', html)
        self.assertIn('href="#경제/거시" class="nav-pill" onclick="document.querySelector(\'.all-articles\').open = true"', html)
        self.assertIn('id="경제/거시" class="section-title"', html)
        self.assertNotIn('href="#정치" class="nav-pill"', html)
        self.assertIn("https://example.com/article", html)
        self.assertNotIn('class="sentiment-box"', html)
        self.assertNotIn('class="keyword-card"', html)

    def test_section_shortcuts_only_link_to_rendered_article_sections(self):
        article = {
            "title": "기사", "link": "https://example.com/shared", "source": "뉴스",
            "published_dt": datetime(2026, 10, 6, 6),
        }
        person = {"이름": {"count": 1, "articles": [article]}}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "index.html"
            HTMLGenerator().generate_main_page(
                {"정치": [article], "부동산": [{**article, "link": "https://example.com/home"}]},
                [article], {}, {}, str(path), "2026.10.06", key_persons=person,
            )
            html = path.read_text(encoding="utf-8")
        self.assertIn('href="#인물별" class="nav-pill"', html)
        self.assertIn('href="#부동산" class="nav-pill"', html)
        self.assertIn('href="#science" class="nav-pill"', html)
        self.assertNotIn('href="#정치" class="nav-pill"', html)

    def test_reader_first_front_page_and_full_archive(self):
        def article(category, index, priority):
            return {
                "title": f"{category} 기사 {index}", "link": f"https://example.com/{category}/{index}",
                "source": "테스트뉴스", "published_dt": datetime(2026, 10, 6, index),
                "priority_score": priority, "pol_subcategory": "기타", "sector": "기타산업",
            }

        data = {category: [article(category, i, 5 if i == 1 else 0) for i in range(1, 6)]
                for category in ("정치", "경제/거시", "부동산", "국제", "기업/산업")}
        brief = {"section_summaries": {category: f"{category} 요약" for category in data}}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "index.html"
            HTMLGenerator().generate_main_page(data, [], brief, {}, str(path), "2026.10.06")
            html = path.read_text(encoding="utf-8")

        front = html.split('<section class="front-page"', 1)[1].split('</section>', 1)[0]
        self.assertEqual(front.count('class="front-page-section"'), 3)
        self.assertEqual(front.count('class="card card-illustrated"'), 9)
        self.assertEqual(front.count('class="card-art"'), 9)
        self.assertIn('aria-hidden="true"', front)
        self.assertNotIn('정치 기사', front)
        self.assertLess(front.index('경제/거시 기사'), front.index('부동산 기사'))
        self.assertLess(front.index('부동산 기사'), front.index('국제 기사'))
        self.assertNotIn('경제/거시 기사 1', front)  # recency takes precedence over score
        self.assertNotIn('경제/거시 기사 2', front)
        self.assertIn('경제/거시 기사 5', front)
        self.assertLess(html.index('경제/거시 요약'), html.index('정치 요약'))
        self.assertLess(html.index('href="#경제/거시" class="nav-pill"'),
                        html.index('href="#정치" class="nav-pill"'))
        full = html.split('<details class="all-articles">', 1)[1]
        parser = SectionParser()
        parser.feed(html)
        self.assertEqual(parser.ids, ["경제/거시", "부동산", "국제", "기업/산업", "정치"])
        self.assertEqual(set(parser.links), set(parser.ids))
        self.assertIn('정치 기사 5', full)
        self.assertIn('경제/거시 기사 2', full)
        self.assertIn('class="front-page-more" href="#경제/거시"', html)

    def test_empty_interests_do_not_create_empty_front_page(self):
        article = {"title": "정치 기사", "link": "https://example.com/politics",
                   "source": "뉴스", "published_dt": datetime(2026, 10, 6, 6),
                   "pol_subcategory": "기타"}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "index.html"
            HTMLGenerator().generate_main_page({"정치": [article]}, [], {}, {}, str(path), "2026.10.06")
            html = path.read_text(encoding="utf-8")
        self.assertNotIn('<section class="front-page"', html)
        self.assertIn('정치 기사', html)

    def test_front_page_does_not_promote_stale_high_score(self):
        now = datetime(2026, 10, 6, 6)
        data = {"부동산": [
            {"title": "지난주 뉴스", "link": "https://example.com/old", "source": "뉴스",
             "published_dt": now - timedelta(days=2), "priority_score": 100},
            {"title": "오늘 뉴스", "link": "https://example.com/new", "source": "뉴스",
             "published_dt": now, "priority_score": 1},
        ]}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "index.html"
            HTMLGenerator().generate_main_page(data, [], {}, {}, str(path), "2026.10.06")
            html = path.read_text(encoding="utf-8")
        front = html.split('<section class="front-page"', 1)[1].split('</section>', 1)[0]
        self.assertIn('오늘 뉴스', front)
        self.assertNotIn('지난주 뉴스', front)
        self.assertIn('지난주 뉴스', html.split('<details class="all-articles">', 1)[1])


if __name__ == "__main__":
    unittest.main()