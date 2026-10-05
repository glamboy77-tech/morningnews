"""Offline regression tests for the daily keyword-to-article contract."""

import unittest

from keyword_analyzer import KeywordAnalyzer


class KeywordArticleMatchingTests(unittest.TestCase):
    def setUp(self):
        self.analyzer = KeywordAnalyzer()

    def test_reason_words_do_not_link_unrelated_missile_story(self):
        articles = {
            "국제": [
                {
                    "title": "北, 동해로 탄도미사일 발사",
                    "link": "https://example.com/north-korea",
                    "source": "뉴스A",
                },
                {
                    "title": "이란 혁명수비대, 미국 위협에 대응",
                    "description": "과거 이란의 탄도미사일 발사를 언급했다",
                    "link": "https://example.com/iran",
                    "source": "뉴스B",
                },
            ]
        }
        item = self.analyzer._build_llm_keyword_item(
            {"keyword": "탄도미사일", "reason": "북한 동해상 발사", "categories": ["국제"]},
            articles,
        )
        self.assertEqual(item["article_count"], 1)
        self.assertEqual(
            [article["link"] for article in item["related_articles"]],
            ["https://example.com/north-korea"],
        )

    def test_category_alone_cannot_select_unrelated_representative(self):
        item = self.analyzer._build_llm_keyword_item(
            {"keyword": "누리호", "reason": "로켓 조립", "categories": ["국제"]},
            {"국제": [{"title": "브라질 도박 규제", "link": "https://example.com/brazil"}]},
        )
        self.assertIsNone(item["representative_article"])
        self.assertEqual(item["related_articles"], [])

    def test_rejects_generic_llm_keyword(self):
        self.assertIsNone(self.analyzer._normalize_llm_candidate_detail({"keyword": "대규모"}))

    def test_matching_topic_without_reason_still_links(self):
        item = self.analyzer._build_llm_keyword_item(
            {"keyword": "누리호", "reason": "", "categories": []},
            {"테크": [{"title": "누리호 5차 발사 준비", "link": "https://example.com/rocket"}]},
        )
        self.assertEqual(item["article_count"], 1)
        self.assertEqual(item["representative_article"]["link"], "https://example.com/rocket")

    def test_hybrid_ranking_drops_unlinked_llm_and_local_candidates(self):
        ranked = self.analyzer.extract_hybrid_keywords(
            {"국제": [{"title": "북한 탄도미사일 발사", "link": "https://example.com/missile"}]},
            llm_candidates=[
                {"keyword": "없는사건", "reason": "북한 발사", "categories": ["국제"]},
                {"keyword": "탄도미사일", "reason": "", "categories": ["국제"]},
            ],
        )
        self.assertEqual([item["keyword"] for item in ranked], ["탄도미사일"])
        self.assertTrue(all(item.get("representative_article") for item in ranked))


if __name__ == "__main__":
    unittest.main()