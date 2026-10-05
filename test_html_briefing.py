"""Offline checks for the short daily reading path."""

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from html_generator import HTMLGenerator


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


if __name__ == "__main__":
    unittest.main()