import os
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv(encoding="utf-8") # Ensure utf-8 for Korean characters

class Config:
    def __init__(self):
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        # Multi-model setup - prioritize FLASH (gemini-3-flash-preview) as requested
        self.model_flash = os.getenv("GEMINI_MODEL_FLASH", "gemini-3-flash-preview")
        self.model_lite = os.getenv("GEMINI_MODEL_LITE", "gemini-3-flash-preview")
        self.model_pro = os.getenv("GEMINI_MODEL_PRO", "gemini-3-flash-preview")
        # Main model version for generic tasks
        self.gemini_version = self.model_flash
        
        # PWA Push Notification (VAPID)
        # 1. Try to read from file first (Safest way)
        if os.path.exists("vapid_private.pem"):
            with open("vapid_private.pem", 'r') as f:
                self.vapid_private_key = f.read().strip()
        else:
            # 2. Fallback to .env (Legacy)
            self.vapid_private_key = os.getenv("VAPID_PRIVATE_KEY")
            if self.vapid_private_key:
                self.vapid_private_key = self.vapid_private_key.strip().strip('"').strip("'").replace('\\n', '\n')
        self.vapid_public_key = os.getenv("VAPID_PUBLIC_KEY", "BKNrtTTrz1YQEk7x1b6mRtb66K2Oebg7d1a592iVbJ1V2Z4pJefsB28WI8dH6l32tSik2JlWOHuwskDb0IsiVLQ")
        self.vapid_email = os.getenv("VAPID_EMAIL", "mailto:your-email@example.com")
        
        self.domestic_feeds = self._parse_feeds_from_file("국내 기사 RSS 주소", "해외 기사 RSS 주소")
        self.international_feeds = self._parse_feeds_from_file("해외 기사 RSS 주소", None)
        self.server_ip = os.getenv("SERVER_IP", "127.0.0.1")
        self.weather_location = os.getenv("WEATHER_LOCATION", "일산")
        
        self.target_keywords = [
            "용산", "국제업무지구", "재개발", "재건축", "모아주택", "가로주택", "일산",
            "1기 신도시", "노후계획도시", "신통기획", "분양가 상한제", "용적률",
            "GTX", "지하화", "신분당선 연장",
            "기준금리", "코픽스", "공사비 증액", "PF 대출"
        ]
        
    def _parse_feeds_from_file(self, start_marker, end_marker):
        """rss_feeds.txt 파일에서 RSS 피드를 읽어옵니다."""
        feeds = {}
        feed_file = "rss_feeds.txt"
        
        # rss_feeds.txt가 없으면 .env에서 fallback
        if not os.path.exists(feed_file):
            return self._parse_feeds_from_env(start_marker, end_marker)
            
        with open(feed_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        capture = False
        for line in lines:
            line = line.strip()
            if not line: continue
            
            # 마커 매칭
            clean_line = line.replace("#", "").replace(" ", "")
            target_start = start_marker.replace(" ", "")
            target_end = end_marker.replace(" ", "") if end_marker else None
            
            if target_start in clean_line:
                capture = True
                continue
            if target_end and target_end in clean_line:
                capture = False
                break
            
            if capture and "=" in line and not line.startswith("#"):
                try:
                    name, url_part = line.split("=", 1)
                    feeds[name.strip()] = url_part.strip().strip('"').strip("'")
                except: continue
        return feeds
    
    def _parse_feeds_from_env(self, start_marker, end_marker):
        """레거시: .env 파일에서 RSS 피드를 읽어옵니다."""
        feeds = {}
        if not os.path.exists(".env"): return feeds
        with open(".env", "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        capture = False
        for line in lines:
            line = line.strip()
            if not line: continue
            
            # More robust marker matching (removes # and spaces)
            clean_line = line.replace("#", "").replace(" ", "")
            target_start = start_marker.replace(" ", "")
            target_end = end_marker.replace(" ", "") if end_marker else None
            
            if target_start in clean_line:
                capture = True
                continue
            if target_end and target_end in clean_line:
                capture = False
                break
            
            if capture and "=" in line and not line.startswith("#"):
                try:
                    name, url_part = line.split("=", 1)
                    feeds[name.strip()] = url_part.strip().strip('"').strip("'")
                except: continue
        return feeds

    @property
    def filter_start_time(self):
        # Yesterday 8:30 AM (KST)
        from datetime import timezone, timedelta
        kst = timezone(timedelta(hours=9))
        now = datetime.now(kst)
        yesterday = now - timedelta(days=1)
        # return as naive datetime for comparison compatibility with pub_dt.replace(tzinfo=None)
        return yesterday.replace(hour=8, minute=30, second=0, microsecond=0).replace(tzinfo=None)

config = Config()

if __name__ == "__main__":
    print(f"Domestic Feeds: {config.domestic_feeds}")
    print(f"International Feeds: {config.international_feeds}")
    print(f"Filter Start Time: {config.filter_start_time}")
