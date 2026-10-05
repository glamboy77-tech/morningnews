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
        self.assertIn("https://example.com/article", html)
        self.assertNotIn('class="sentiment-box"', html)
        self.assertNotIn('class="keyword-card"', html)


if __name__ == "__main__":
    unittest.main()