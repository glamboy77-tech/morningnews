import os
import sys
import datetime
from rss_manager import RSSManager
from ai_processor import AIProcessor
from html_generator import HTMLGenerator
from sentiment_analyzer import SentimentAnalyzer
from data_cache import DataCache

from weather_manager import WeatherManager
from notifier import send_telegram_hojae
from archive_generator import generate_archive
from retrofit_output_pages import retrofit_output_pages

# 콘솔과 파일에 동시 출력
class DualLogger:
    def __init__(self, file_path, mode='a'):
        self.file = open(file_path, mode, encoding='utf-8', buffering=1)
        self.console = sys.stdout
        
    def write(self, msg):
        self.console.write(msg)
        self.file.write(msg)
        self.console.flush()
        self.file.flush()
        
    def flush(self):
        self.console.flush()
        self.file.flush()

sys.stdout = DualLogger('run_job.log', 'a')
sys.stderr = DualLogger('run_job.log', 'a')

RUN_STATE_DIR = ".run_state"

def _ensure_run_state_dir():
    os.makedirs(RUN_STATE_DIR, exist_ok=True)

def get_done_marker_path(date_str: str) -> str:
    return os.path.join(RUN_STATE_DIR, f"done_{date_str}.json")

def has_done_marker(date_str: str) -> bool:
    return os.path.exists(get_done_marker_path(date_str))

def write_done_marker(date_str: str, payload: dict):
    _ensure_run_state_dir()
    marker_path = get_done_marker_path(date_str)
    tmp_path = f"{marker_path}.tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            import json
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, marker_path)
        print(f"✅ done marker 생성: {marker_path}")
    except Exception as e:
        print(f"⚠️ done marker 생성 실패: {e}")

def get_missing_required_outputs(date_str: str, output_path: str, cache: DataCache, sentiment: SentimentAnalyzer):
    missing = []
    if not cache.has_cache("rss", date_str):
        missing.append("data_cache/rss")
    if not cache.has_cache("ai_analysis", date_str):
        missing.append("data_cache/ai_analysis")
    if not cache.has_cache("key_persons", date_str):
        missing.append("data_cache/key_persons")
    if not os.path.exists(sentiment.get_cache_filename(date_str)):
        missing.append("sentiment_cache/sentiment")
    if not os.path.exists(output_path):
        missing.append("output/morning_news")
    return missing

def main(send_push=True, use_cache=True, *, ignore_done_marker: bool = False, tts_only: bool = False, scripts_only: bool = False):
    print("=== Morning News Bot Started ===")

    # 시간대 통일: GitHub Actions는 기본 UTC로 실행되므로, 모든 판단/캐시 키는 KST 기준으로 맞춘다.
    kst = datetime.timezone(datetime.timedelta(hours=9))
    now_kst = datetime.datetime.now(kst)

    # Initialize cache system
    cache = DataCache()
    today_str = now_kst.strftime("%Y%m%d")

    # done marker 기반 LLM 스킵 (운영 모드에서만)
    if use_cache and not ignore_done_marker and has_done_marker(today_str) and not scripts_only:
        required_missing = get_missing_required_outputs(
            today_str,
            os.path.join("output", f"morning_news_{today_str}.html"),
            cache,
            SentimentAnalyzer(),
        )
        if not required_missing:
            print(f"⏭️ done marker 발견: {get_done_marker_path(today_str)}")
            print("🚫 오늘은 이미 완료되어 LLM 호출을 수행하지 않습니다.")
            return
        print(f"⚠️ done marker는 있으나 누락 산출물 존재: {', '.join(required_missing)}")
        print("➡️ 누락 산출물 재생성을 위해 작업을 계속 진행합니다.")
    
    # 캐시 상태 확인
    cache_status = cache.get_cache_status(today_str)
    print(f"📊 오늘의 캐시 상태: RSS={cache_status['rss']}, AI분석={cache_status['ai_analysis']}, 인물={cache_status['key_persons']}")
    
    # 1. Setup (KST 기준)
    date_str_dot = now_kst.strftime("%Y.%m.%d")
    date_str_file = now_kst.strftime("%Y%m%d")
    
    # Output Directory
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    
    main_filename = f"morning_news_{date_str_file}.html"
    main_file_path = os.path.join(output_dir, main_filename)
    
    # Initialize managers
    rss = RSSManager()
    ai = AIProcessor()
    sentiment = SentimentAnalyzer()
    html_gen = HTMLGenerator()
    wm = WeatherManager()
    
    if tts_only or scripts_only:
        print("\n[Phase 1~2.5] TTS-only 모드: 캐시된 데이터만 사용합니다.")
        if not (cache_status["rss"] and cache_status["ai_analysis"] and cache_status["key_persons"]):
            print("⚠️ TTS-only 모드에 필요한 캐시가 없습니다. 먼저 전체 실행으로 캐시를 생성하세요.")
            print("   예: python main.py --no-push")
            return
        print("🔄 캐시된 RSS 데이터 로드 중...")
        all_news = cache.load_rss_data(today_str) or []
        print("🔄 캐시된 AI 분석 데이터 로드 중...")
        domestic_categorized_raw = cache.load_ai_analysis(today_str) or {}
        print("🔄 캐시된 주요 인물 데이터 로드 중...")
        key_persons = cache.load_key_persons(today_str) or {}
        weather_data = wm.get_weather()
    else:
        # 2. Fetch Feeds & Weather (시간 기반 캐시 로직)
        print("\n[Phase 1] Fetching RSS Feeds & Weather...")
    
        if use_cache and cache_status["rss"]:
            print("🔄 캐시된 RSS 데이터 로드 중...")
            all_news = cache.load_rss_data(today_str)
            if all_news:
                print(f"  - 캐시된 RSS 로드: {len(all_news)}건")
            else:
                print("  - 캐시 로드 실패, 새로 수집...")
                all_news = rss.fetch_feeds()
                if use_cache:
                    cache.save_rss_data(all_news, today_str)
        else:
            all_news = rss.fetch_feeds()
            if use_cache:
                cache.save_rss_data(all_news, today_str)
        
        weather_data = wm.get_weather()
        print(f"  - Total feeds fetched: {len(all_news)}")
        
        domestic_raw_all = [n for n in all_news if n['category'] == 'domestic']
        print(f"  - Total domestic articles: {len(domestic_raw_all)}")
        
        # Separate Science Times
        science_raw = [n for n in domestic_raw_all if "사이언스타임즈" in n['source']]
        domestic_raw = [n for n in domestic_raw_all if "사이언스타임즈" not in n['source']]
        print(f"  - Science articles: {len(science_raw)}")
        print(f"  - Non-science domestic articles: {len(domestic_raw)}")
        
        # Sort and limit Science Times to latest 10
        science_raw.sort(key=lambda x: x['published_dt'], reverse=True)
        science_raw = science_raw[:10]
        
        # Sort general news by date to ensure recent ones are prioritized across all sources
        domestic_raw.sort(key=lambda x: x['published_dt'], reverse=True)
        
        # 배치 처리: 200개씩 나눠서 AI 분류 후 병합
        batch_size = 200
        domestic_categorized_raw = {}
        
        # 3. AI Processing (시간 기반 캐시 로직)
        print("\n[Phase 2] AI Processing...")
        
        if use_cache and cache_status["ai_analysis"]:
            print("🔄 캐시된 AI 분석 데이터 로드 중...")
            domestic_categorized_raw = cache.load_ai_analysis(today_str)
            if domestic_categorized_raw:
                print(f"  - 캐시된 AI 분석 로드: {sum(len(v) for v in domestic_categorized_raw.values())}건")
            else:
                print("  - 캐시 로드 실패, 새로 분석...")
                for batch_start in range(0, len(domestic_raw), batch_size):
                    batch_end = min(batch_start + batch_size, len(domestic_raw))
                    batch = domestic_raw[batch_start:batch_end]
                    print(f"  - Processing batch: articles {batch_start+1}~{batch_end} ({len(batch)} articles)")
                    
                    batch_result = ai.process_domestic_news(batch)
                    
                    # 배치 결과를 전체 결과에 병합
                    for category, items in batch_result.items():
                        if category not in domestic_categorized_raw:
                            domestic_categorized_raw[category] = []
                        domestic_categorized_raw[category].extend(items)
                if use_cache:
                    cache.save_ai_analysis(domestic_categorized_raw, today_str)
        else:
            for batch_start in range(0, len(domestic_raw), batch_size):
                batch_end = min(batch_start + batch_size, len(domestic_raw))
                batch = domestic_raw[batch_start:batch_end]
                print(f"  - Processing batch: articles {batch_start+1}~{batch_end} ({len(batch)} articles)")
                
                batch_result = ai.process_domestic_news(batch)
                
                # 배치 결과를 전체 결과에 병합
                for category, items in batch_result.items():
                    if category not in domestic_categorized_raw:
                        domestic_categorized_raw[category] = []
                    domestic_categorized_raw[category].extend(items)
            if use_cache:
                cache.save_ai_analysis(domestic_categorized_raw, today_str)
        
        total_returned = sum(len(v) for v in domestic_categorized_raw.values())
        print(f"  - AI returned {total_returned} articles across {len(domestic_categorized_raw)} categories.")
        
        # Apply "At least 20" logic per category
        domestic_categorized = {}
        from config import config
        start_time = config.filter_start_time
        
        for category, items in domestic_categorized_raw.items():
            # Separate recent and older
            recent_items = [it for it in items if it['published_dt'] >= start_time]
            older_items = [it for it in items if it['published_dt'] < start_time]
            
            # Keep all items (remove minimum threshold)
            # If there are at least some recent items, prefer them over older ones
            if recent_items:
                domestic_categorized[category] = recent_items
            else:
                # Use older items only if no recent items exist
                domestic_categorized[category] = older_items
        
        # Count valid domestic items
        domestic_count = sum(len(items) for items in domestic_categorized.values())
        print(f"  - Classified {domestic_count} domestic articles (with fallback).")
        print(f"  - Domestic Categories: {list(domestic_categorized.keys())}")
    
        # 3.5. Extract Key Persons (시간 기반 캐시 로직)
        print("\n[Phase 2.5] Extracting Key Persons...")
        
        if use_cache and cache_status["key_persons"]:
            print("🔄 캐시된 주요 인물 데이터 로드 중...")
            key_persons = cache.load_key_persons(today_str)
            # NOTE: 빈 dict({})도 '정상 로드(인물 없음)'일 수 있으므로 None 여부로 판단
            if key_persons is not None:
                print(f"  - 캐시된 주요 인물 로드: {len(key_persons)}명")
            else:
                print("  - 캐시 로드 실패, 새로 추출...")
                key_persons = ai.extract_key_persons(domestic_categorized)
                if key_persons is not None and use_cache:
                    cache.save_key_persons(key_persons, today_str)
        else:
            key_persons = ai.extract_key_persons(domestic_categorized)
            if key_persons is not None and use_cache:
                cache.save_key_persons(key_persons, today_str)
        
        if key_persons:
            print(f"  - Found {len(key_persons)} key persons:")
            for person_name, person_data in key_persons.items():
                print(f"    · {person_name} ({person_data['role']}): {person_data['count']}건")
        else:
            print("  - No key persons found with 3+ articles")

    if tts_only or scripts_only:
        domestic_raw_all = [n for n in all_news if n.get('category') == 'domestic']
        science_raw = [n for n in domestic_raw_all if "사이언스타임즈" in n.get('source', '')]
        science_raw.sort(key=lambda x: x['published_dt'], reverse=True)
        science_raw = science_raw[:10]

        domestic_categorized = {}
        from config import config
        start_time = config.filter_start_time
        for category, items in domestic_categorized_raw.items():
            recent_items = [it for it in items if it['published_dt'] >= start_time]
            older_items = [it for it in items if it['published_dt'] < start_time]
            domestic_categorized[category] = recent_items if recent_items else older_items
        domestic_count = sum(len(items) for items in domestic_categorized.values())
 
    # 4. Generate Briefing (SentimentAnalyzer는 항상 실행)
    print("\n[Phase 3] Generating Morning Briefing...")
    briefing_data = None
    if use_cache and os.path.exists(sentiment.get_cache_filename(today_str)):
        print("🔄 캐시된 감성/브리핑 데이터 로드 중...")
        briefing_data = sentiment.load_cached_data(today_str)

    if isinstance(briefing_data, dict):
        briefing_data = sentiment.sanitize_briefing_data(briefing_data, today_str)
    if tts_only or scripts_only:
        if briefing_data is None:
            print("⚠️ TTS-only 모드인데 오늘 감성/브리핑 캐시가 없습니다. 먼저 전체 실행을 진행하세요.")
            print("   예: python main.py --no-push")
            return
        try:
            if scripts_only:
                briefing_data = sentiment.ensure_brief_scripts(
                    briefing_data,
                    today_str,
                    categorized_news=domestic_categorized,
                    max_retries=3,
                )
            else:
                briefing_data = sentiment.regenerate_tts_only(
                    briefing_data,
                    today_str,
                    categorized_news=domestic_categorized,
                    max_retries=3,
                )
            if use_cache:
                sentiment.save_cached_data(briefing_data, today_str)
        except Exception as e:
            print(f"⚠️ TTS-only 재생성 실패: {e}")
            return
    elif briefing_data is None:
        # 당일 브리핑/스크립트가 반드시 생성되도록 stale 캐시 사용 금지
        briefing_data = sentiment.analyze_sentiment(
            domestic_categorized,
            today_str,
            use_cache=use_cache,
            allow_stale=False,
            max_retries=3,
        )

    # Save YouTube TTS script (separate text file) - always on
    tts_path = sentiment.save_tts_script_text(briefing_data, today_str)
    if tts_path:
        tts_lines = briefing_data.get("tts_script", {}).get("lines", []) if briefing_data else []
        print(f"✅ TTS 스크립트 저장 완료: {tts_path} (lines={len(tts_lines)})")
    else:
        print("⚠️ TTS 스크립트 저장 실패 또는 데이터 없음")

    # Save brief source_script JSON (single output)
    brief_scripts = briefing_data.get("brief_scripts") if isinstance(briefing_data, dict) else None
    if isinstance(brief_scripts, dict) and isinstance(brief_scripts.get("source_script"), str):
        brief_path = sentiment.save_brief_scripts_json(brief_scripts, today_str)
        if brief_path:
            print(f"✅ 브리프 스크립트 저장 완료: {brief_path}")
        else:
            print("⚠️ 브리프 스크립트 저장 실패")

        keyword_path = sentiment.save_keywords_text(brief_scripts.get("keywords"), today_str)
        if keyword_path:
            print(f"✅ 키워드 파일 저장 완료: {keyword_path}")
        else:
            print("⚠️ 키워드 파일 저장 실패 또는 키워드 데이터 없음")

    # Save shorts scripts JSON (derived from brief source script)
    shorts_scripts = briefing_data.get("shorts_scripts") if isinstance(briefing_data, dict) else None
    if isinstance(shorts_scripts, dict) and shorts_scripts.get("items"):
        shorts_path = sentiment.save_shorts_scripts_json(shorts_scripts, today_str)
        if shorts_path:
            print(f"✅ 쇼츠 스크립트 저장 완료: {shorts_path}")
        else:
            print("⚠️ 쇼츠 스크립트 저장 실패")

        shorts_txt_path = sentiment.save_shorts_scripts_text(shorts_scripts, today_str)
        if shorts_txt_path:
            print(f"✅ 쇼츠 TXT 저장 완료: {shorts_txt_path}")
        else:
            print("⚠️ 쇼츠 TXT 저장 실패")

    if scripts_only:
        print("\n=== Finished Scripts-Only Successfully ===")
        return
 
    # 5. Generate Main HTML
    print("\n[Phase 4] Generating Main HTML...")
    # 최신 템플릿 반영을 위해 오늘자 페이지와 index.html은 항상 재생성한다.
    html_gen.generate_main_page(
        domestic_categorized,
        science_raw,
        briefing_data,
        weather_data,
        main_file_path,
        date_str_dot,
        key_persons
    )

    # Also generate index.html in root folder (as a copy of the latest report)
    index_file_path = "index.html"
    html_gen.generate_main_page(
        domestic_categorized,
        science_raw,
        briefing_data,
        weather_data,
        index_file_path,
        date_str_dot,
        key_persons
    )

    # 5.0 Retrofit old output pages for GitHub Pages subpath + Archive nav
    try:
        print("\n[Phase 4.0] Retrofitting old output pages...")
        changed = retrofit_output_pages(output_dir)
        print(f"  - Retrofitted files: {changed}")
    except Exception as e:
        print(f"⚠️ output 페이지 보정 실패: {e}")

    # 5.1 Generate archive page (list of previous daily HTML files)
    try:
        print("\n[Phase 4.1] Generating Archive Page...")
        generate_archive(output_dir=output_dir, archive_path="archive.html")
    except Exception as e:
        print(f"⚠️ archive.html 생성 실패: {e}")

    # 5.5 텔레그램 호재 기업 알림 (선택적)
    try:
        total_articles = domestic_count + len(science_raw)
        send_telegram_hojae(briefing_data, date_str_dot, total_articles)
    except Exception as e:
        print(f"⚠️ 텔레그램 알림 실패: {e}")
    
    # 6. Push Notification 기능 제거
    if send_push:
        print("\n[Phase 5] Push 알림 기능은 제거되어 더 이상 발송하지 않습니다.")
    else:
        print("\n[Phase 5] Push 알림 기능 제거됨 (--no-push 옵션은 하위 호환용).")
    print("\n=== Finished Successfully ===")

    # done marker 생성 (모든 필수 산출물 완비 시에만)
    if use_cache:
        missing = get_missing_required_outputs(today_str, main_file_path, cache, sentiment)
        if not missing:
            write_done_marker(
                today_str,
                {
                    "date": today_str,
                    "created_at": now_kst.isoformat(),
                    "output": main_file_path,
                },
            )
        else:
            print(f"⚠️ done marker 보류: 누락된 산출물 -> {', '.join(missing)}")

if __name__ == "__main__":
    # 커맨드라인 인자: --no-push, --no-cache, --ignore-done-marker, --tts-only, --scripts-only
    send_push = True
    use_cache = True
    ignore_done_marker = False
    tts_only = False
    scripts_only = False
    
    for arg in sys.argv[1:]:
        if arg == "--no-push":
            send_push = False
        elif arg == "--no-cache":
            use_cache = False
        elif arg == "--ignore-done-marker":
            ignore_done_marker = True
        elif arg == "--tts-only":
            tts_only = True
        elif arg == "--scripts-only":
            scripts_only = True
    
    main(
        send_push,
        use_cache,
        ignore_done_marker=ignore_done_marker,
        tts_only=tts_only,
        scripts_only=scripts_only,
    )
