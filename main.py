import os
import sys
import datetime
from rss_manager import RSSManager
from ai_processor import AIProcessor
from html_generator import HTMLGenerator

from weather_manager import WeatherManager
from notifier import send_notification

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

def main(send_push=True):
    print("=== Morning News Bot Started ===")
    
    # 1. Setup (한국 시간 KST 설정)
    # UTC 기준 시각에 9시간 더해서 한국 시간 계산합니다
    kst = datetime.timezone(datetime.timedelta(hours=9))
    today = datetime.datetime.now(kst)
    
    date_str_dot = today.strftime("%Y.%m.%d")
    date_str_file = today.strftime("%Y%m%d")
    
    # Output Directory
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    
    main_filename = f"morning_news_{date_str_file}.html"
    main_file_path = os.path.join(output_dir, main_filename)
    
    rss = RSSManager()
    ai = AIProcessor()
    html_gen = HTMLGenerator()
    wm = WeatherManager()
    
    # 2. Fetch Feeds & Weather
    print("\n[Phase 1] Fetching RSS Feeds & Weather...")
    all_news = rss.fetch_feeds()
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
    
    # 매체별로 그룹화
    from collections import defaultdict
    key = lambda x: (x['source'], x['section']) if 'section' in x else (x['source'], x.get('category',''))
    grouped = defaultdict(list)
    for idx, item in enumerate(domestic_raw):
        grouped[key(item)].append((idx, item))
    print(f"  - Media groups: {len(grouped)}")

    # 1차 호출: 모든 기사 제목을 AI에 보내서 필터링
    # (데이터 크기 관리용으로 매체별 최대 N개씩만 먼저 선택)
    articles_for_filtering = []
    for group_key, group_items in grouped.items():
        group_news = [item for idx, item in group_items]
        group_news.sort(key=lambda x: x['published_dt'], reverse=True)
        # 각 매체/섹션별로 최대 100개까지 1차 필터링 대상에 포함
        top_n = min(100, len(group_news))
        articles_for_filtering.extend(group_news[:top_n])
    
    print(f"  - 1차 필터링 대상 기사 수: {len(articles_for_filtering)}")
    
    # 1차 필터링: 제목으로 중요도 판단
    filtered_indices = ai.filter_important_titles(articles_for_filtering, top_k=len(articles_for_filtering))
    filtered_domestic = [articles_for_filtering[i] for i in filtered_indices]
    print(f"  - 1차 필터링 후 기사 수: {len(filtered_domestic)}")

    # 2차: 본문 포함 AI 분류
    domestic_categorized_raw = ai.process_domestic_news(filtered_domestic)
    
    # Debug: see what AI returned
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
 
    # 4. Generate Briefing
    print("\n[Phase 3] Generating Morning Briefing...")
    briefing_data = ai.generate_briefing(domestic_categorized)
 
    # 5. Generate Main HTML
    print("\n[Phase 4] Generating Main HTML...")
    # Generate date-specific file
    html_gen.generate_main_page(
        domestic_categorized, 
        science_raw, 
        briefing_data,
        weather_data, 
        main_file_path, 
        date_str_dot
    )
    
    # Also generate index.html in root folder (as a copy of the latest report)
    index_file_path = "index.html"
    html_gen.generate_main_page(
        domestic_categorized, 
        science_raw, 
        briefing_data,
        weather_data, 
        index_file_path, 
        date_str_dot
    )
    
    # 6. Send Push Notification
    if send_push:
        print("\n[Phase 5] Sending Push Notification...")
        total_articles = domestic_count + len(science_raw)
        send_notification(date_str_dot, total_articles, main_filename)
    else:
        print("\n[Phase 5] (테스트 모드) 알림은 발송하지 않습니다.")
    print("\n=== Finished Successfully ===")

if __name__ == "__main__":
    # 커맨드라인 인자: --no-push
    send_push = True
    if len(sys.argv) > 1 and sys.argv[1] == "--no-push":
        send_push = False
    main(send_push)
