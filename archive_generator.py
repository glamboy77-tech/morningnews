import os
import re
from datetime import datetime


NEWS_FILE_RE = re.compile(r"^morning_news_(\d{8})\.html$")


def _format_date(yyyymmdd: str) -> str:
    try:
        dt = datetime.strptime(yyyymmdd, "%Y%m%d")
        return dt.strftime("%Y.%m.%d")
    except Exception:
        return yyyymmdd


def generate_archive(output_dir: str = "output", archive_path: str = "archive.html", max_items: int | None = None):
    """Generate a simple archive page listing daily news HTML files.

    Designed for GitHub Pages (subpath) compatibility by using relative links.
    """
    if not os.path.isdir(output_dir):
        raise FileNotFoundError(f"Output dir not found: {output_dir}")

    items: list[tuple[str, str]] = []  # (yyyymmdd, filename)
    for fn in os.listdir(output_dir):
        m = NEWS_FILE_RE.match(fn)
        if not m:
            continue
        items.append((m.group(1), fn))

    # 최신순
    items.sort(key=lambda x: x[0], reverse=True)
    if max_items is not None:
        items = items[: max_items]

    links_html = "\n".join(
        [
            f'<a class="item" href="output/{fn}"><span class="date">{_format_date(date)}</span><span class="arrow">›</span></a>'
            for date, fn in items
        ]
    )
    if not links_html:
        links_html = '<div class="empty">아직 생성된 뉴스가 없습니다.</div>'

    html = f"""<!DOCTYPE html>
<html lang=\"ko\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>Morning News Archive</title>
  <link rel=\"manifest\" href=\"manifest.json\" />
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&family=Outfit:wght@100;300;400;600;900&display=swap');
    :root {{
      --bg: #050505;
      --surface: rgba(255,255,255,0.04);
      --surface2: rgba(255,255,255,0.07);
      --text: #ffffff;
      --muted: #a0a0a0;
      --primary: #4facfe;
      --border: rgba(255,255,255,0.10);
    }}
    * {{ box-sizing: border-box; -webkit-tap-highlight-color: transparent; }}
    body {{
      margin: 0;
      font-family: 'Outfit','Noto Sans KR',sans-serif;
      background: radial-gradient(circle at 50% 0%, #1a1a1a 0%, #050505 100%);
      color: var(--text);
    }}
    .container {{ max-width: 600px; margin: 0 auto; padding: 20px 20px 80px; }}
    .header {{
      margin-top: 10px;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 24px;
      padding: 18px 18px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }}
    .title {{ font-weight: 700; letter-spacing: 0.2px; }}
    .subtitle {{ color: var(--muted); font-size: 0.85rem; font-weight: 300; }}
    .btn {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 10px 14px;
      border-radius: 999px;
      border: 1px solid var(--border);
      color: var(--text);
      text-decoration: none;
      background: transparent;
    }}
    .btn:active {{ background: var(--surface2); }}
    .list {{ margin-top: 16px; display: flex; flex-direction: column; gap: 10px; }}
    .item {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 16px 16px;
      text-decoration: none;
      color: var(--text);
      display: flex;
      align-items: center;
      justify-content: space-between;
      transition: 0.2s ease;
    }}
    .item:active {{ background: var(--surface2); }}
    .date {{ color: var(--primary); font-weight: 700; letter-spacing: 0.5px; }}
    .arrow {{ color: var(--muted); font-size: 1.4rem; line-height: 1; }}
    .empty {{ color: var(--muted); padding: 20px 8px; text-align: center; }}
    footer {{ margin-top: 28px; text-align: center; color: #333; font-size: 0.7rem; letter-spacing: 2px; }}
  </style>
  <script>
    // Service Worker Registration (GitHub Pages subpath-safe)
    if ('serviceWorker' in navigator) {{
      navigator.serviceWorker.register('sw.js')
        .then(reg => console.log('Service Worker registered:', reg))
        .catch(err => console.error('Service Worker registration failed:', err));
    }}
  </script>
</head>
<body>
  <div class=\"container\">
    <div class=\"header\">
      <div>
        <div class=\"title\">🗓️ 아카이브</div>
        <div class=\"subtitle\">이전 날짜 모닝뉴스를 선택하세요</div>
      </div>
      <a class=\"btn\" href=\"index.html\">← 오늘 뉴스</a>
    </div>
    <div class=\"list\">
      {links_html}
    </div>
    <footer>&copy; 2025 PREMIUM MORNING NEWS BOT</footer>
  </div>
</body>
</html>
"""

    with open(archive_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Generated {archive_path} ({len(items)} items)")


if __name__ == "__main__":
    generate_archive()
