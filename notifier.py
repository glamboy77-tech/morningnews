import json
import base64
import os
import requests
from pywebpush import webpush, WebPushException
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

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


def send_telegram_hojae(briefing_data, date_str=None):
    """Send Hojae list to Telegram if credentials exist."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("ℹ️ TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID가 없어 텔레그램 전송을 건너뜁니다.")
        return

    hojae_list = briefing_data.get("hojae", []) if briefing_data else []
    if not hojae_list:
        print("ℹ️ 호재 리스트가 없어 텔레그램 전송을 건너뜁니다.")
        return

    title = f"📈 호재 기업 리스트 ({date_str})" if date_str else "📈 호재 기업 리스트"
    lines = [title]
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

if __name__ == "__main__":
    import os
    send_notification()
