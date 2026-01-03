import feedparser
from datetime import datetime
from time import mktime
from config import config

class RSSManager:
    def __init__(self):
        self.config = config

    def fetch_feeds(self):
        """
        Fetches all feeds and returns a list of dictionaries.
        Each item has: title, link, source, published, published_struct, description
        """
        all_news = []

        # 1. Domestic Feeds
        print("Fetching Domestic Feeds...")
        for source_name, url in self.config.domestic_feeds.items():
            try:
                feed = feedparser.parse(url)
                print(f"  - {source_name}: {len(feed.entries)} entries found.")
                
                for entry in feed.entries:
                    # Parse date
                    published = entry.get('published_parsed') or entry.get('updated_parsed')
                    if not published:
                        continue
                        
                    import calendar
                    from datetime import timezone, timedelta
                    
                    # feedparser.published_parsed is in UTC
                    utc_secs = calendar.timegm(published)
                    pub_dt = datetime.fromtimestamp(utc_secs, tz=timezone.utc).astimezone(timezone(timedelta(hours=9)))
                    # Strip timezone info for legacy code compatibility if needed, or keep for accuracy
                    pub_dt = pub_dt.replace(tzinfo=None)
                    
                    # Store all articles, we will filter/limit later in main.py
                    all_news.append({
                        'title': entry.get('title', 'No Title'),
                        'link': entry.get('link', ''),
                        'source': source_name,
                        'published_dt': pub_dt,
                        'description': entry.get('description', ''),
                        'category': 'domestic' 
                    })
            except Exception as e:
                print(f"Error fetching {source_name}: {e}")
                
        return all_news

if __name__ == "__main__":
    manager = RSSManager()
    news = manager.fetch_feeds()
    print(f"Total entries fetched: {len(news)}")
    for item in news[:5]:
        print(f"[{item['source']}] {item['title']} ({item['published_dt']})")
