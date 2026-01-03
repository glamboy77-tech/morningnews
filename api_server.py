from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os

app = Flask(__name__)
CORS(app)  # CORS 허용

SUBSCRIPTIONS_FILE = 'subscriptions.json'

@app.route('/api/save-subscription', methods=['POST'])
def save_subscription():
    try:
        subscription = request.json
        
        if not subscription:
            return jsonify({'error': 'No subscription data provided'}), 400
        
        # 기존 구독 정보 로드
        subscriptions = []
        if os.path.exists(SUBSCRIPTIONS_FILE):
            with open(SUBSCRIPTIONS_FILE, 'r', encoding='utf-8') as f:
                try:
                    subscriptions = json.load(f)
                except json.JSONDecodeError:
                    subscriptions = []
        
        # 중복 체크 (endpoint 기준)
        endpoint = subscription.get('endpoint')
        if endpoint:
            # 같은 endpoint가 이미 있는지 확인
            existing = [s for s in subscriptions if s.get('endpoint') == endpoint]
            if existing:
                return jsonify({'message': 'Already subscribed', 'subscription': subscription}), 200
        
        # 새 구독 추가
        subscriptions.append(subscription)
        
        # 파일에 저장
        with open(SUBSCRIPTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(subscriptions, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 새로운 구독 저장됨! 총 구독자: {len(subscriptions)}명")
        return jsonify({'message': 'Subscription saved successfully', 'total': len(subscriptions)}), 200
        
    except Exception as e:
        print(f"❌ 구독 저장 에러: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/subscriptions', methods=['GET'])
def get_subscriptions():
    """구독 정보 확인용 (디버깅)"""
    try:
        if os.path.exists(SUBSCRIPTIONS_FILE):
            with open(SUBSCRIPTIONS_FILE, 'r', encoding='utf-8') as f:
                subscriptions = json.load(f)
                return jsonify({'count': len(subscriptions), 'subscriptions': subscriptions}), 200
        else:
            return jsonify({'count': 0, 'subscriptions': []}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok'}), 200

if __name__ == '__main__':
    print("🚀 API 서버 시작...")
    print("📍 엔드포인트: http://localhost:5000/api/save-subscription")
    app.run(host='0.0.0.0', port=5000, debug=True)
