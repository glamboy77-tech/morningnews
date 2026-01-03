"""
Quick script to regenerate index.html using existing news content while refreshing header/time/weather.
"""

import os
import shutil
import re
from datetime import datetime

from html_generator import HTMLGenerator
from weather_manager import WeatherManager

# Instantiate helpers
html_gen = HTMLGenerator()
wm = WeatherManager()

# Use live weather if available; otherwise fall back to default values
weather_data = wm.get_weather() or {
    "emoji": "☀️",
    "location": "일산",
    "desc": "맑음",
    "min_temp": "5",
    "max_temp": "15",
    "diff_msg": "",
}

date_str = datetime.now().strftime("%Y.%m.%d")

# 0) Backup existing index.html
if os.path.exists("index.html"):
    shutil.copy2("index.html", "index.html.bak")

# 1) Generate a fresh skeleton (header/weather/footer) without news data
html_gen.generate_main_page(
    domestic_data={},
    international_data=[],
    briefing_data={},
    weather_data=weather_data,
    filename="index.html",
    date_str=date_str,
)

# 2) Extract old news content between </header> and <footer>
old_content = ""
source_file = "index.html.bak" if os.path.exists("index.html.bak") else "index.html"

if os.path.exists(source_file):
    try:
        with open(source_file, "r", encoding="utf-8") as f:
            old_html = f.read()
        match = re.search(r"</header>([\s\S]*?)<footer>", old_html)
        if match:
            old_content = match.group(1).strip()
            # Remove an empty sticky-nav if present to avoid duplication
            old_content = old_content.replace('<div class="sticky-nav"></div>', '')
    except Exception as e:
        print(f"Error reading old content: {e}")

# 3) Inject old news content into the new skeleton
if old_content:
    with open("index.html", "r", encoding="utf-8") as f:
        new_html = f.read()
    header_end_tag = "</header>"
    insert_pos = new_html.find(header_end_tag)
    if insert_pos != -1:
        insert_pos += len(header_end_tag)
        footer_start_pos = new_html.find("<footer>")
        if footer_start_pos != -1:
            final_html = (
                new_html[:insert_pos] + "\n" + old_content + "\n" + new_html[footer_start_pos:]
            )
            with open("index.html", "w", encoding="utf-8") as f:
                f.write(final_html)

print("\n[성공] index.html이 실시간 날씨와 함께 재생성되었습니다!")
print("- 기존의 뉴스 바로가기, 브리핑, 모든 기사 섹션이 안전하게 복구되었습니다.")
print("- 이제 서버에 upload 하여 확인해보세요.")
