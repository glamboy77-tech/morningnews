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

    def test_briefing_lead_is_short_and_remaining_text_is_expandable(self):
        summary = '첫 번째 핵심 소식입니다. 두 번째 소식도 있습니다. 마지막 내용입니다.'
        briefing = {'section_summaries': {'경제/거시': summary, '국제': '짧은 한 문장입니다.'}}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'index.html'
            HTMLGenerator().generate_main_page({}, [], briefing, {}, str(path), '2026.10.06')
            html = path.read_text(encoding='utf-8')
        card = html.split('<div class="briefing-card">', 1)[1].split('<!--', 1)[0]
        self.assertIn('<span class="briefing-content">첫 번째 핵심 소식입니다.</span>', card)
        self.assertIn('<details class="briefing-more"><summary>자세히 보기</summary>', card)
        self.assertIn('<p>두 번째 소식도 있습니다. 마지막 내용입니다.</p>', card)
        self.assertEqual(html.count('class="briefing-more"'), 1)
        self.assertIn('<span class="briefing-content">짧은 한 문장입니다.</span>', html)

    def test_briefing_preserves_numbers_and_escapes_untrusted_text(self):
        summary = '매출은 3.5% 늘었습니다. <script>alert("x")</script> 다음 문장입니다.'
        lead = HTMLGenerator._briefing_summary_html(summary)
        self.assertIn('3.5% 늘었습니다.</span>', lead)
        self.assertIn('&lt;script&gt;', lead)
        self.assertNotIn('<script>', lead)
        self.assertEqual(HTMLGenerator._briefing_summary_html('문장 구분 없음'),
                         '<span class="briefing-content">문장 구분 없음</span>')

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
            topic = {"경제/거시": "금리", "부동산": "재건축", "국제": "미국"}.get(category, "")
            return {
                "title": f"{category} {topic} 기사 {index}", "link": f"https://example.com/{category}/{index}",
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
        self.assertLess(front.index('경제/거시 금리 기사'), front.index('부동산 재건축 기사'))
        self.assertLess(front.index('부동산 재건축 기사'), front.index('국제 미국 기사'))
        self.assertIn('경제/거시 금리 기사 1', front)  # score outranks recency within 24 hours
        self.assertNotIn('경제/거시 금리 기사 2', front)
        self.assertIn('경제/거시 금리 기사 5', front)
        self.assertLess(html.index('경제/거시 요약'), html.index('정치 요약'))
        self.assertLess(html.index('href="#경제/거시" class="nav-pill"'),
                        html.index('href="#정치" class="nav-pill"'))
        full = html.split('<details class="all-articles">', 1)[1]
        parser = SectionParser()
        parser.feed(html)
        self.assertEqual(parser.ids, ["경제/거시", "부동산", "국제", "기업/산업", "정치"])
        self.assertEqual(set(parser.links), set(parser.ids))
        self.assertIn('정치  기사 5', full)
        self.assertIn('경제/거시 금리 기사 2', full)
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
            {"title": "지난주 재건축 뉴스", "link": "https://example.com/old", "source": "뉴스",
             "published_dt": now - timedelta(days=2), "priority_score": 100},
            {"title": "오늘 재건축 뉴스", "link": "https://example.com/new", "source": "뉴스",
             "published_dt": now, "priority_score": 1},
        ]}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "index.html"
            HTMLGenerator().generate_main_page(data, [], {}, {}, str(path), "2026.10.06")
            html = path.read_text(encoding="utf-8")
        front = html.split('<section class="front-page"', 1)[1].split('</section>', 1)[0]
        self.assertIn('오늘 재건축 뉴스', front)
        self.assertNotIn('지난주 재건축 뉴스', front)
        self.assertIn('지난주 재건축 뉴스', html.split('<details class="all-articles">', 1)[1])

    def test_front_page_skips_sales_pitch_but_keeps_it_in_full_list(self):
        now = datetime(2026, 10, 8, 7)
        sale = {"title": "지금 가장 달고 아삭한 사과는 ‘양광’, 특품인데 5kg 22개 5만원대 단독 특가",
                "link": "https://example.com/sale", "source": "뉴스",
                "published_dt": now, "priority_score": 100}
        news = [{"title": f"금리 현안 {i}", "link": f"https://example.com/news/{i}",
                 "source": "뉴스", "published_dt": now - timedelta(minutes=i)}
                for i in range(1, 4)]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "index.html"
            HTMLGenerator().generate_main_page({"경제/거시": [sale, *news]}, [], {}, {},
                                               str(path), "2026.10.08")
            html = path.read_text(encoding="utf-8")
        front = html.split('<section class="front-page"', 1)[1].split('</section>', 1)[0]
        self.assertNotIn('단독 특가', front)
        self.assertEqual(front.count('class="card card-illustrated"'), 3)
        self.assertIn('금리 현안 3', front)
        self.assertIn('단독 특가', html.split('<details class="all-articles">', 1)[1])

    def test_front_page_prefers_significant_event_over_newer_minor_story(self):
        now = datetime(2026, 10, 8, 7)
        fresh = {"title": "중산층 가계부채 현황", "link": "https://example.com/new",
                 "source": "뉴스", "published_dt": now, "priority_score": 0}
        important = {"title": "중앙은행 기준금리 인하 결정", "link": "https://example.com/important",
                     "source": "뉴스", "published_dt": now - timedelta(hours=6), "priority_score": 1}
        directory = {"title": "충북지역 주요 금융시장 경제통계 | 뉴스/자료 | 한국은행 홈페이지",
                     "link": "https://example.com/directory", "source": "공식",
                     "published_dt": now - timedelta(hours=3), "priority_score": 100}
        picks = HTMLGenerator._front_page_picks(
            [fresh, important, directory], '경제/거시', set())
        self.assertEqual([item['link'] for item in picks],
                         ['https://example.com/important', 'https://example.com/new'])

    def test_front_page_excludes_off_topic_even_if_it_has_a_high_source_score(self):
        now = datetime(2026, 10, 8, 7)
        events = [
            {"title": "국회 조달청 군수품 관리 계획", "link": "https://example.com/off",
             "published_dt": now, "priority_score": 100},
            {"title": "미국, 이란 제재 확대 결정", "link": "https://example.com/on",
             "published_dt": now - timedelta(hours=1), "priority_score": 0},
        ]
        self.assertEqual([item['link'] for item in HTMLGenerator._front_page_picks(
            events, '국제', set())], ['https://example.com/on'])

    def test_editorial_news_mentioning_advertising_is_not_a_sales_pitch(self):
        self.assertFalse(HTMLGenerator._is_sales_promotion(
            {'title': '정부 광고 예산을 둘러싼 논란'}))
        self.assertFalse(HTMLGenerator._is_sales_promotion(
            {'title': '사과 가격 상승에 농가 부담 커져'}))
        self.assertFalse(HTMLGenerator._is_sales_promotion(
            {'title': '지역 유통업체 특가 행사, 매출 10% 증가'}))
        self.assertTrue(HTMLGenerator._is_sales_promotion(
            {'title': '이번 주 한정 특가 제품 구매하세요'}))


if __name__ == "__main__":
    unittest.main()