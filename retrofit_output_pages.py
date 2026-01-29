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

    # Gemini Navigator overlay patch
    gemini_js = r"""
              // --- Gemini Navigator Overlay (in-app) ---
              const GEMINI_NAV_URL = 'https://gemini-783885185452.us-west1.run.app/?embed=1';
              let geminiLoaded = false;
              let geminiLoadTimer = null;

              function setGeminiLoading(isLoading) {
                  const loading = document.getElementById('geminiLoading');
                  if (!loading) return;
                  loading.style.display = isLoading ? 'flex' : 'none';
              }

              function startGeminiLoadTimer() {
                  if (geminiLoadTimer) clearTimeout(geminiLoadTimer);
                  geminiLoadTimer = setTimeout(() => {
                      if (!geminiLoaded) {
                          setGeminiLoading(false);
                      }
                  }, 15000);
              }

              function openGeminiNavigator() {
                  const overlay = document.getElementById('geminiOverlay');
                  const frame = document.getElementById('geminiFrame');
                  if (!overlay || !frame) return;

                  // show
                  overlay.classList.add('open');
                  document.body.classList.add('no-scroll');

                  // reset loading state
                  setGeminiLoading(!geminiLoaded);
                  startGeminiLoadTimer();

                  // set src lazily (avoid background CPU)
                  // NOTE: iframe.src property is auto-resolved even when attribute is "".
                  // Use the attribute value to decide whether we've already loaded Gemini.
                  const srcAttr = frame.getAttribute('src');
                  if (!srcAttr || srcAttr === 'about:blank') frame.setAttribute('src', GEMINI_NAV_URL);
              }

              function closeGeminiNavigator() {
                  const overlay = document.getElementById('geminiOverlay');
                  if (!overlay) return;
                  overlay.classList.remove('open');
                  document.body.classList.remove('no-scroll');
              }

              function openGeminiInNewTab() {
                  window.open('https://gemini-783885185452.us-west1.run.app/', '_blank', 'noopener,noreferrer');
              }

              function reloadGeminiNavigator() {
                  const frame = document.getElementById('geminiFrame');
                  if (!frame) return;
                  geminiLoaded = false;
                  setGeminiLoading(true);
                  startGeminiLoadTimer();
                  frame.setAttribute('src', `${GEMINI_NAV_URL}&t=${Date.now()}`);
              }

              document.addEventListener('keydown', (e) => {
                  if (e.key === 'Escape') closeGeminiNavigator();
              });
    """.strip()

    js_pattern = r"// --- Gemini Navigator Overlay \(in-app\) ---[\s\S]*?document\.addEventListener\('keydown', \(e\) => \{[\s\S]*?\}\);"
    html, _ = re.subn(js_pattern, gemini_js, html, count=1)

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

    # 4) Update Gemini overlay buttons (add reload)
    actions_pattern = r"<div class=\"gemini-overlay-actions\">[\s\S]*?</div>"
    actions_html = (
        '<div class="gemini-overlay-actions">'
        '<button class="gemini-icon-btn" type="button" title="새로고침" onclick="reloadGeminiNavigator()">↻</button>'
        '<button class="gemini-icon-btn" type="button" title="새 창으로 열기" onclick="openGeminiInNewTab()">↗</button>'
        '<button class="gemini-icon-btn" type="button" title="닫기" onclick="closeGeminiNavigator()">✕</button>'
        '</div>'
    )
    html, _ = re.subn(actions_pattern, actions_html, html, count=1)

    # 5) Update iframe onload handler to mark loaded state
    html = html.replace(
        "onload=\"document.getElementById('geminiLoading').style.display='none'\"",
        "onload=\"geminiLoaded = true; setGeminiLoading(false);\"",
    )

    # 6) Allow microphone in Gemini iframe (cross-origin permission delegation)
    html = html.replace(
        'referrerpolicy="no-referrer" onload="geminiLoaded = true; setGeminiLoading(false);"',
        'referrerpolicy="no-referrer" allow="microphone; camera; autoplay" onload="geminiLoaded = true; setGeminiLoading(false);"',
    )

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
