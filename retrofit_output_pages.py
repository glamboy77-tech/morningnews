"""Retrofit older generated HTML pages in output/ for GitHub Pages subpath & archive UX.

Why:
- Historical files were generated with absolute paths like '/sw.js' which break on
  GitHub Pages subpaths (e.g. https://.../morningnews/).
- Add an Archive nav link so users can always go back inside a fullscreen PWA.

This script is idempotent.
"""

import os
import re


OUTPUT_DIR = "output"


def retrofit_file(path: str) -> bool:
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()

    original = html

    # 1) Fix manifest path
    html = html.replace('rel="manifest" href="manifest.json"', 'rel="manifest" href="../manifest.json"')

    # 2) Fix SW registration path patterns
    # Common patterns:
    # - register('/sw.js')
    # - register("/sw.js")
    html = re.sub(r"register\((['\"])\/sw\.js\1\)", r"register(\1../sw.js\1)", html)

    # 3) Insert archive link into sticky-nav (if not already)
    if '🗓️ 아카이브' not in html:
        # Insert right after Gemini nav pill
        gemini = '<a href="#" class="nav-pill" onclick="openGeminiNavigator(); return false;">🔎 Gemini 네비게이터</a>'
        if gemini in html:
            html = html.replace(gemini, gemini + '<a href="../archive.html" class="nav-pill">🗓️ 아카이브</a>')

    changed = html != original
    if changed:
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
    return changed


def retrofit_output_pages(output_dir: str = OUTPUT_DIR) -> int:
    if not os.path.isdir(output_dir):
        return 0

    changed_count = 0
    for fn in os.listdir(output_dir):
        if not (fn.startswith("morning_news_") and fn.endswith(".html")):
            continue
        path = os.path.join(output_dir, fn)
        try:
            if retrofit_file(path):
                changed_count += 1
        except Exception as e:
            print(f"⚠️ retrofit failed: {path}: {e}")
    return changed_count


if __name__ == "__main__":
    cnt = retrofit_output_pages()
    print(f"Retrofit complete. Changed {cnt} files.")
