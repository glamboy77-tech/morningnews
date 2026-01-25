import os
import sys
import datetime
from rss_manager import RSSManager
from ai_processor import AIProcessor
from html_generator import HTMLGenerator
from sentiment_analyzer import SentimentAnalyzer
from data_cache import DataCache

from weather_manager import WeatherManager
from notifier import send_notification, send_telegram_hojae

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

def main(send_push=True, use_cache=True):
    print("=== Morning News Bot Started ===")

    # 시간대 통일: GitHub Actions는 기본 UTC로 실행되므로, 모든 판단/캐시 키는 KST 기준으로 맞춘다.
    kst = datetime.timezone(datetime.timedelta(hours=9))
    now_kst = datetime.datetime.now(kst)

    # 현재 시간 확인 (KST)
    current_hour = now_kst.hour
    is_morning_window = 8 <= current_hour < 9  # 오전 8시~9시 (KST)
    
    # 캐시 사용 로직: 오전 8-9시는 새로 생성, 그 외 시간은 캐시 재사용
    if is_morning_window:
        print(f"🌅 오전 {current_hour}시: 새로운 뉴스 생성 및 캐시 저장")
        use_cache_for_loading = False  # 새로 생성
    else:
        print(f"🕐 {current_hour}시: 캐시된 뉴스 재사용")
        use_cache_for_loading = True   # 캐시 재사용
    
    # 테스트 모드 확인
    is_test_mode = not send_push
    if is_test_mode and not is_morning_window:
        print("🧪 테스트 모드: 데이터 캐시 재사용 활성화")
    
    # Initialize cache system
    cache = DataCache()
    today_str = now_kst.strftime("%Y%m%d")
    
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
    
    # 2. Fetch Feeds & Weather (시간 기반 캐시 로직)
    print("\n[Phase 1] Fetching RSS Feeds & Weather...")
    
    if use_cache and cache_status["rss"] and use_cache_for_loading:
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
    
    if use_cache and cache_status["ai_analysis"] and use_cache_for_loading:
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
    
    if use_cache and cache_status["key_persons"] and use_cache_for_loading:
        print("🔄 캐시된 주요 인물 데이터 로드 중...")
        key_persons = cache.load_key_persons(today_str)
        if key_persons:
            print(f"  - 캐시된 주요 인물 로드: {len(key_persons)}명")
        else:
            print("  - 캐시 로드 실패, 새로 추출...")
            key_persons = ai.extract_key_persons(domestic_categorized)
            if use_cache:
                cache.save_key_persons(key_persons, today_str)
    else:
        key_persons = ai.extract_key_persons(domestic_categorized)
        if use_cache:
            cache.save_key_persons(key_persons, today_str)
    
    if key_persons:
        print(f"  - Found {len(key_persons)} key persons:")
        for person_name, person_data in key_persons.items():
            print(f"    · {person_name} ({person_data['role']}): {person_data['count']}건")
    else:
        print("  - No key persons found with 3+ articles")
 
    # 4. Generate Briefing (SentimentAnalyzer는 항상 실행)
    print("\n[Phase 3] Generating Morning Briefing...")
    briefing_data = sentiment.analyze_sentiment(domestic_categorized)
 
    # 5. Generate Main HTML
    print("\n[Phase 4] Generating Main HTML...")
    # Generate date-specific file
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

    # 5.5 텔레그램 호재 기업 알림 (선택적)
    try:
        total_articles = domestic_count + len(science_raw)
        send_telegram_hojae(briefing_data, date_str_dot, total_articles)
    except Exception as e:
        print(f"⚠️ 텔레그램 알림 실패: {e}")
    
    # 6. Send Push Notification
    if send_push:
        print("\n[Phase 5] Sending Push Notification...")
        total_articles = domestic_count + len(science_raw)
        send_notification(date_str_dot, total_articles, main_filename)
    else:
        print("\n[Phase 5] (테스트 모드) 알림은 발송하지 않습니다.")
    print("\n=== Finished Successfully ===")

if __name__ == "__main__":
    # 커맨드라인 인자: --no-push, --no-cache
    send_push = True
    use_cache = True
    
    for arg in sys.argv[1:]:
        if arg == "--no-push":
            send_push = False
        elif arg == "--no-cache":
            use_cache = False
    
    main(send_push, use_cache)
