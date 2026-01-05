import json
import base64
import os
import re
import glob
import requests
from dotenv import load_dotenv
from pywebpush import webpush, WebPushException
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

# Load environment variables (supports Korean characters)
load_dotenv(encoding="utf-8")

def send_notification(date_str=None, count=None, filename=None):
    try:
        # 1. 구독 정보 로드
        if not os.path.exists('subscriptions.json'):
            print("❌ subscriptions.json 파일이 없습니다.")
            return
            
        with open('subscriptions.json', 'r') as f:
            subscriptions = json.load(f)
        
        if not subscriptions:
            print("❌ 구독 정보가 없습니다. 폰에서 '알림 받기'를 먼저 눌러주세요.")
            return

        # 2. 비밀키 읽기 및 RAW 추출
        key_file = 'vapid_private.pem'
        if not os.path.exists(key_file):
            print(f"❌ {key_file} 파일이 없습니다.")
            return
            
        with open(key_file, 'rb') as f:
            pem_data = f.read()

        # RAW 키 추출 (pywebpush가 가장 좋아하는 형식)
        try:
            priv_key_obj = serialization.load_pem_private_key(pem_data, password=None, backend=default_backend())
            # EC 키에서 raw 32바이트 추출
            priv_num = priv_key_obj.private_numbers().private_value
            # P-256은 32바이트입니다.
            raw_priv_bytes = priv_num.to_bytes(32, 'big')
            # Base64URL (no padding)
            private_key_for_send = base64.urlsafe_b64encode(raw_priv_bytes).decode('utf-8').rstrip('=')
            print("✅ VAPID 키 로드 및 RAW 추출 성공")
        except Exception as ve:
            print(f"❌ VAPID 키 처리 실패: {ve}")
            return

        # 4. 마지막 구독자에게 발송
        latest_sub = subscriptions[-1]
        print(f"[PUSH] 총 {len(subscriptions)}명의 구독자 중 마지막 구독자에게 전송 중...")
        
        webpush(
            subscription_info=latest_sub,
            data="🏠 모닝뉴스가 도착했습니다! 새로운 뉴스를 확인하세요.",
            vapid_private_key=private_key_for_send,
            vapid_claims={"sub": "mailto:ohnboy@naver.com"}
        )
        print("✅ 전송 성공!")


    except WebPushException as ex:
        print(f"❌ 푸시 서버 에러: {ex}")
        if ex.response and ex.response.json():
            print(f"   상세: {ex.response.json()}")
    except Exception as e:
        print(f"❌ 일반 에러 발생: {e}")


def send_telegram_hojae(briefing_data, date_str=None, total_news_count=None):
    """Send Hojae list to Telegram with a short update summary."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("ℹ️ TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID가 없어 텔레그램 전송을 건너뜁니다.")
        return

    hojae_list = briefing_data.get("hojae", []) if briefing_data else []
    hojae_count = len(hojae_list)
    if not hojae_list:
        print("ℹ️ 호재 리스트가 없어 텔레그램 전송을 건너뜁니다.")
        return

    # Compose summary header (date, total news, hojae count)
    headline = "📰 모닝뉴스가 업데이트되었습니다"
    if date_str:
        headline += f" ({date_str})"

    summary_parts = []
    if total_news_count is not None:
        summary_parts.append(f"총 {total_news_count}건의 뉴스")
    summary_parts.append(f"호재 기업: {hojae_count}곳")
    summary_line = " / ".join(summary_parts)

    list_title = f"📈 호재 기업 리스트 ({date_str})" if date_str else "📈 호재 기업 리스트"

    lines = [headline, summary_line, "", list_title]
    for item in hojae_list:
        lines.append(f"- {item}")
    message = "\n".join(lines)

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message}
        )
        if resp.status_code == 200:
            print("✅ 텔레그램 전송 성공")
        else:
            print(f"❌ 텔레그램 전송 실패: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"❌ 텔레그램 전송 중 오류: {e}")


def _extract_hojae_from_html(html_path):
    """Parse existing HTML to extract hojae list, date, and news count."""
    if not html_path or not os.path.exists(html_path):
        print(f"❌ HTML 파일을 찾을 수 없습니다: {html_path}")
        return None

    try:
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()
    except Exception as e:
        print(f"❌ HTML 파일을 읽는 중 오류: {e}")
        return None

    # Extract hojae block
    hojae_block = None
    m = re.search(r'sentiment-type\s+hojae[^<]*</span>\s*<div class="sentiment-items">(.*?)</div>\s*</div>', html, re.S)
    if m:
        hojae_block = m.group(1)
    if not hojae_block:
        print("ℹ️ HTML에서 호재 블록을 찾지 못했습니다.")
        return None

    hojae_list = re.findall(r'<div class="sentiment-item">(.*?)</div>', hojae_block)
    hojae_list = [item.strip() for item in hojae_list if item.strip()]
    if not hojae_list:
        print("ℹ️ HTML에서 호재 항목을 찾지 못했습니다.")
        return None

    # Date from filename (morning_news_YYYYMMDD.html) or title (Morning News YYYY.MM.DD)
    date_str = None
    m = re.search(r'morning_news_(\d{8})', os.path.basename(html_path))
    if m:
        y, mo, d = m.group(1)[:4], m.group(1)[4:6], m.group(1)[6:]
        date_str = f"{y}.{mo}.{d}"
    else:
        m = re.search(r'Morning News (\d{4}\.\d{2}\.\d{2})', html)
        if m:
            date_str = m.group(1)

    # Count news: prefer nav-pill totals, fallback to card divs
    total_news_count = 0
    nav_counts = [int(x) for x in re.findall(r'class="nav-pill"[^>]*>[^<]*\((\d+)\)', html)]
    if nav_counts:
        total_news_count = sum(nav_counts)
    else:
        total_news_count = len(re.findall(r'class="card[^\"]*"', html))

    return {
        "briefing_data": {"hojae": hojae_list},
        "date_str": date_str,
        "total_news_count": total_news_count,
    }


def send_telegram_from_html(html_path=None):
    """Send Telegram using already-generated HTML without regenerating news."""
    target_path = html_path
    if not target_path:
        candidates = sorted(glob.glob(os.path.join("output", "morning_news_*.html")))
        if not candidates:
            print("❌ output 폴더에 생성된 뉴스 HTML이 없습니다.")
            return
        target_path = candidates[-1]

    extracted = _extract_hojae_from_html(target_path)
    if not extracted:
        return

    send_telegram_hojae(
        extracted["briefing_data"],
        extracted.get("date_str"),
        extracted.get("total_news_count"),
    )

if __name__ == "__main__":
    import sys

    # CLI: python notifier.py --send-telegram-from-html [path]
    if len(sys.argv) >= 2 and sys.argv[1] == "--send-telegram-from-html":
        html_arg = sys.argv[2] if len(sys.argv) >= 3 else None
        send_telegram_from_html(html_arg)
    else:
        send_notification()
