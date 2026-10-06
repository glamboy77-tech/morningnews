"""RSS article preview and image opt-in checks (offline)."""

import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from article_preview import permitted_image, rss_image_url, rss_preview
from html_generator import HTMLGenerator
from rss_manager import RSSManager


class ArticlePreviewTests(unittest.TestCase):
    def test_rss_preview_removes_markup_and_duplicate_title(self):
        self.assertEqual(rss_preview('<img src="https://test.invalid/x.jpg"><p>오늘 &amp; 내일, '
                                     '부동산 시장에 새 소식이 있습니다. 새 거래 동향도 살펴봅니다.</p>'),
                         '오늘 & 내일, 부동산 시장에 새 소식이 있습니다. 새 거래 동향도 살펴봅니다.')
        self.assertEqual(rss_preview('<b>제목만 반복되는 기사</b>', '제목만 반복되는 기사'), '')
        self.assertEqual(rss_preview('<script>악성 스크립트</script><p>짧음</p>'), '')
        self.assertTrue(rss_preview('한글' * 100).endswith('…'))

    def test_image_extraction_rejects_untrusted_schemes_and_nonimages(self):
        self.assertEqual(rss_image_url({'media_thumbnail': [{'url': 'https://media.test/pic.jpg'}]}),
                         'https://media.test/pic.jpg')
        self.assertEqual(rss_image_url({'description': '<img src="https://media.test/photo.webp">'}),
                         'https://media.test/photo.webp')
        self.assertEqual(rss_image_url({'description': '<img src="javascript:alert(1)">'}), '')
        self.assertEqual(rss_image_url({'description': '<img src="https://media.test/track.gif">'}), '')

    def test_rss_ingestion_keeps_article_description_and_image_candidate(self):
        entry = {'title': '오늘의 경제 기사', 'link': 'https://publisher.test/story',
                 'description': '<img src="https://media.test/photo.jpg">'
                                '<p>오늘 시장에 변화가 생겼으며 원문에서 배경을 더 자세히 확인할 수 있습니다.</p>',
                 'published_parsed': (2026, 10, 6, 0, 0, 0, 1, 279, 0)}
        manager = RSSManager()
        manager.config = type('Config', (), {'domestic_feeds': {'테스트매체': 'https://publisher.test/rss'}})()
        with patch('rss_manager.feedparser.parse', return_value=type('Feed', (), {'entries': [entry]})()):
            articles = manager.fetch_feeds()
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]['image_url'], 'https://media.test/photo.jpg')
        self.assertEqual(articles[0]['description'], entry['description'])

    def test_images_are_off_by_default_and_require_source_and_host(self):
        item = {'source': '허용한 매체', 'image_url': 'https://media.test/pic.jpg'}
        with patch.dict(os.environ, {'MORNINGNEWS_IMAGE_SOURCES': '', 'MORNINGNEWS_IMAGE_HOSTS': ''}):
            self.assertEqual(permitted_image(item), '')
        with patch.dict(os.environ, {'MORNINGNEWS_IMAGE_SOURCES': '허용한 매체',
                                      'MORNINGNEWS_IMAGE_HOSTS': 'media.test'}):
            self.assertEqual(permitted_image(item), 'https://media.test/pic.jpg')
            self.assertEqual(permitted_image({**item, 'source': '다른 매체'}), '')
            self.assertEqual(permitted_image({**item, 'image_url': 'https://media.test.attacker/pic.jpg'}), '')
            self.assertEqual(permitted_image({**item, 'image_url': 'http://media.test/pic.jpg'}), '')
            self.assertEqual(permitted_image({**item, 'image_url': 'https://media.test/track.gif'}), '')

    def test_page_renders_escaped_excerpts_and_opted_in_photos(self):
        item = {'title': '경제 기사', 'link': 'https://example.test/article',
                'source': '허용한 매체', 'published_dt': datetime(2026, 10, 6, 6),
                'description': '<img src="https://media.test/photo.jpg">'
                               '<p>경제에 영향을 미치는 기사 &amp; 추가 정보가 있습니다. '
                               '&lt;script&gt;danger&lt;/script&gt;</p>',
                'image_url': 'https://media.test/photo.jpg'}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'index.html'
            with patch.dict(os.environ, {'MORNINGNEWS_IMAGE_SOURCES': '허용한 매체',
                                          'MORNINGNEWS_IMAGE_HOSTS': 'media.test'}):
                HTMLGenerator().generate_main_page({'경제/거시': [item]}, [], {}, {}, str(path), '2026.10.06')
            rendered = path.read_text(encoding='utf-8')
        self.assertIn('class="card-preview"', rendered)
        self.assertIn(".card-preview::before { content: 'RSS 미리보기 · ';", rendered)
        self.assertIn('경제에 영향을 미치는 기사 &amp; 추가 정보', rendered)
        self.assertNotIn('<script>danger</script>', rendered)
        self.assertIn('class="article-photo" src="https://media.test/photo.jpg"', rendered)
        self.assertIn('사진: 허용한 매체 RSS', rendered)
        self.assertIn('this.nextElementSibling.hidden=false', rendered)
        self.assertIn("querySelector('.article-photo-credit').hidden=true", rendered)
        self.assertIn('class="card-art" hidden', rendered)


if __name__ == '__main__':
    unittest.main()