import json
import os
import sys
from datetime import datetime, timezone, timedelta

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from config import config
from rss_manager import RSSManager
from ai_processor import AIProcessor
from sentiment_analyzer import SentimentAnalyzer


def _build_sample_news(limit: int = 25):
    rss = RSSManager()
    all_news = rss.fetch_feeds()
    domestic = [n for n in all_news if n.get("category") == "domestic"]
    domestic.sort(key=lambda x: x.get("published_dt"), reverse=True)
    return domestic[:limit]


def _run_briefing(model_name: str, categorized_news: dict, date_str: str):
    analyzer = SentimentAnalyzer()
    analyzer.client = analyzer.client  # keep client, but swap model in config
    original_model = config.model_flash
    try:
        config.model_flash = model_name
        briefing = analyzer.analyze_sentiment(
            categorized_news,
            date_str,
            use_cache=False,
            allow_stale=False,
            max_retries=2,
        )
        return briefing
    finally:
        config.model_flash = original_model


def main():
    kst = timezone(timedelta(hours=9))
    today_str = datetime.now(kst).strftime("%Y%m%d")
    sample_news = _build_sample_news()

    if not sample_news:
        print("❌ 샘플 뉴스가 없습니다.")
        return

    processor = AIProcessor()
    categorized = processor.process_domestic_news(sample_news)
    if not categorized:
        print("❌ 분류 결과가 없습니다.")
        return

    models = [
        config.model_flash,
        config.model_pro,
        config.model_lite,
    ]

    results = {}
    for model in models:
        print(f"\n=== 모델 비교 시작: {model} ===")
        results[model] = _run_briefing(model, categorized, today_str)

    os.makedirs("output", exist_ok=True)
    out_path = os.path.join("output", f"llm_compare_{today_str}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"✅ LLM 비교 결과 저장: {out_path}")


if __name__ == "__main__":
    main()