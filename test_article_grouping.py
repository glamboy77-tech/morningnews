"""Offline checks that similar stories take one card without losing their links."""

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from article_grouping import group_articles
from html_generator import HTMLGenerator


class ArticleGroupingTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 6, 9)

    def article(self, title, link, hours=0):
        return {'title': title, 'link': link, 'source': '뉴스',
                'published_dt': self.now + timedelta(hours=hours)}

    def test_merges_close_titles_and_preserves_sources_without_mutation(self):
        first = self.article('서울 재건축 시공사 입찰 다시 유찰', 'https://a.test/one')
        second = self.article('서울 재건축 시공사 입찰 다시 유찰', 'https://b.test/two', 1)
        original = [first, second]
        grouped = group_articles(original)
        self.assertEqual(len(grouped), 1)
        self.assertEqual(grouped[0]['related_full_sources'][0]['link'], second['link'])
        self.assertNotIn('related_full_sources', first)

    def test_separates_different_events_numbers_and_old_reports(self):
        first = self.article('서울 재건축 시공사 입찰 다시 유찰', 'https://a.test/one')
        different = self.article('부산 재건축 시공사 입찰 다시 유찰', 'https://b.test/two')
        numbers = self.article('서울 재건축 시공사 입찰 2차 유찰', 'https://c.test/three')
        old = self.article(first['title'], 'https://d.test/four', -48)
        self.assertEqual(len(group_articles([first, different, numbers, old])), 4)

    def test_merges_minor_title_extension_without_discarding_existing_related(self):
        first = self.article('서울 재건축 시공사 입찰 다시 유찰', 'https://a.test/one')
        first['related_full_sources'] = [
            {'link': 'https://c.test/three', 'title': first['title'], 'source': '기존 매체'}]
        second = self.article('서울 재건축 시공사 입찰 다시 유찰 소식', 'https://b.test/two')
        grouped = group_articles([first, second])
        self.assertEqual(len(grouped), 1)
        self.assertEqual({entry['link'] for entry in grouped[0]['related_full_sources']},
                         {'https://b.test/two', 'https://c.test/three'})

    def test_page_shows_one_card_and_expands_other_link(self):
        first = self.article('서울 재건축 시공사 입찰 다시 유찰', 'https://a.test/one')
        second = self.article(first['title'], 'https://b.test/two')
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'index.html'
            HTMLGenerator().generate_main_page({'부동산': [first, second]}, [], {}, {},
                                               str(path), '2026.10.06')
            html = path.read_text(encoding='utf-8')
        full = html.split('<details class="all-articles">', 1)[1]
        self.assertEqual(full.count('<div class="card '), 1)
        self.assertIn('관련 기사 1건 더 보기', full)
        self.assertIn('href="https://b.test/two"', full)
        self.assertIn('부동산 (1)', html)

    def test_related_links_escape_markup_and_reject_script_urls(self):
        html = HTMLGenerator._related_articles_html({
            'link': 'https://a.test/one',
            'related_full_sources': [
                {'link': 'javascript:alert(1)', 'title': 'bad', 'source': 'bad'},
                {'link': 'https://b.test/?x=1&y=2', 'title': '<unsafe>', 'source': '매체'},
            ],
        })
        self.assertNotIn('javascript:', html)
        self.assertIn('https://b.test/?x=1&amp;y=2', html)
        self.assertIn('&lt;unsafe&gt;', html)


if __name__ == '__main__':
    unittest.main()