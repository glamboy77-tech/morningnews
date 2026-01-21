import os

class HTMLGenerator:
    def __init__(self):
        self.css = """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&family=Outfit:wght@100;300;400;600;900&family=Russo+One&display=swap');
            
            :root {
                --bg-color: #050505;
                --surface: rgba(255, 255, 255, 0.03);
                --surface-hover: rgba(255, 255, 255, 0.08);
                --primary: #4facfe;
                --text: #ffffff;
                --text-secondary: #a0a0a0;
                --border: rgba(255, 255, 255, 0.1);
                --nav-bg: rgba(5, 5, 5, 0.8);
                --card-priority-bg: rgba(79, 172, 254, 0.05);
                --card-priority-border: #4facfe;
                --related-bg: rgba(255, 255, 255, 0.02);
                --transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            }

            * {
                box-sizing: border-box;
                -webkit-tap-highlight-color: transparent;
            }

            body {
                font-family: 'Outfit', 'Noto Sans KR', sans-serif;
                background-color: var(--bg-color);
                background: radial-gradient(circle at 50% 0%, #1a1a1a 0%, #050505 100%);
                color: var(--text);
                margin: 0;
                padding: 0;
                line-height: 1.6;
                word-break: keep-all;
            }

            .container {
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
                padding-bottom: 100px;
            }

            header {
                text-align: center;
                margin-bottom: 50px;
                padding: 60px 20px;
                background: linear-gradient(135deg, rgba(255, 255, 255, 0.05) 0%, rgba(255, 255, 255, 0.01) 100%);
                backdrop-filter: blur(30px);
                border-radius: 40px;
                border: 1px solid var(--border);
                position: relative;
                overflow: hidden;
                box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5);
            }

            header::before {
                content: '';
                position: absolute;
                top: -50%;
                left: -50%;
                width: 200%;
                height: 200%;
                background: radial-gradient(circle, rgba(79,172,254,0.15) 0%, transparent 60%);
                z-index: 0;
                animation: pulse 8s ease-in-out infinite alternate;
            }

            @keyframes pulse {
                from { transform: scale(1); opacity: 0.5; }
                to { transform: scale(1.1); opacity: 0.8; }
            }

            .header-meta {
                position: relative;
                z-index: 1;
                display: flex;
                flex-direction: column;
                gap: 5px;
                margin-bottom: 15px;
            }

            .header-date {
                font-size: 0.85rem;
                font-weight: 300;
                letter-spacing: 2px;
                color: var(--primary);
                text-transform: uppercase;
            }

            .header-time {
                font-size: 0.7rem;
                color: var(--text-secondary);
                letter-spacing: 1px;
            }

            header h1 {
                position: relative;
                z-index: 1;
                margin: 20px 0;
                font-size: 3.5rem;
                font-family: 'Russo One', sans-serif;
                font-weight: 400;
                text-transform: none;
                letter-spacing: 1px;
                line-height: 1;
                color: #eeeeee;
                /* 은은하고 차분한 글로우로 변경 */
                text-shadow: 0 0 10px rgba(255, 255, 255, 0.2), 
                             0 0 20px rgba(79, 172, 254, 0.1);
                display: block;
            }

            .header-date {
                font-size: 0.9rem;
                font-weight: 600;
                letter-spacing: 1px;
                color: #4facfe;
                margin-bottom: 4px;
            }

            .header-time {
                font-size: 0.8rem;
                color: var(--text-secondary);
                font-weight: 300;
            }

            .section-title {
                font-size: 1.1rem;
                font-weight: 600;
                margin: 40px 0 20px;
                color: var(--text);
                display: flex;
                align-items: center;
                gap: 12px;
                letter-spacing: 0.5px;
            }
            
            .section-title::after {
                content: '';
                flex: 1;
                height: 1px;
                background: linear-gradient(90deg, var(--border), transparent);
            }

            .card {
                background: var(--surface);
                border-radius: 20px;
                padding: 20px;
                margin-bottom: 16px;
                border: 1px solid var(--border);
                transition: var(--transition);
                text-decoration: none;
                display: block;
                color: inherit;
                backdrop-filter: blur(10px);
            }
            
            .card:hover {
                transform: translateY(-4px);
                background: var(--surface-hover);
                border-color: rgba(255, 255, 255, 0.2);
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
            }

            .card-title {
                font-weight: 400;
                font-size: 1.1rem;
                line-height: 1.4;
                margin-bottom: 12px;
                display: -webkit-box;
                -webkit-line-clamp: 2;
                -webkit-box-orient: vertical;
                overflow: hidden;
                color: #efefef;
            }

            .card-meta {
                font-size: 0.8rem;
                color: var(--text-secondary);
                display: flex;
                justify-content: space-between;
                align-items: center;
                font-weight: 300;
            }

            .tag {
                color: var(--primary);
                font-size: 0.75rem;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 1px;
            }

            /* Briefing Card */
            .briefing-card {
                background: var(--surface);
                padding: 24px;
                border-radius: 24px;
                margin-bottom: 40px;
                border: 1px solid var(--border);
                backdrop-filter: blur(10px);
            }
            .briefing-title {
                font-weight: 600;
                font-size: 1rem;
                margin-bottom: 20px;
                color: var(--primary);
                display: flex;
                align-items: center;
                gap: 8px;
                text-transform: uppercase;
                letter-spacing: 1.5px;
            }
            .briefing-item {
                font-size: 0.95rem;
                margin-bottom: 12px;
                display: flex;
                gap: 12px;
                align-items: flex-start;
                line-height: 1.5;
            }
            .briefing-label {
                font-weight: 600;
                min-width: 65px;
                color: var(--text);
                font-size: 0.85rem;
            }
            .briefing-content {
                color: var(--text-secondary);
                font-weight: 300;
            }

            .sentiment-box {
                margin-top: 24px;
                padding-top: 20px;
                border-top: 1px solid var(--border);
            }
            .sentiment-row {
                display: flex;
                margin-bottom: 12px;
                font-size: 0.85rem;
            }
            .sentiment-type {
                font-weight: 600;
                margin-right: 15px;
                min-width: 50px;
            }
            .sentiment-items {
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
            }
            .sentiment-item {
                background: var(--related-bg);
                padding: 4px 10px;
                border-radius: 8px;
                border: 1px solid var(--border);
                font-weight: 300;
            }
            .hojae { color: #ff4b4b; } 
            .akjae { color: #4facfe; } 

            /* Sticky Nav */
            .sticky-nav {
                position: sticky;
                top: 0;
                background: var(--nav-bg);
                backdrop-filter: blur(20px);
                z-index: 1000;
                padding: 12px 20px;
                display: flex;
                flex-wrap: wrap;
                justify-content: flex-start;
                gap: 8px;
                border-bottom: 1px solid var(--border);
            }
            
            .nav-pill {
                padding: 8px 16px;
                border-radius: 100px;
                font-size: 0.8rem;
                color: var(--text-secondary);
                text-decoration: none;
                white-space: nowrap;
                transition: var(--transition);
                font-weight: 400;
                border: 1px solid transparent;
            }
            .nav-pill:active, .nav-pill.active {
                background: var(--surface-hover);
                color: var(--text);
                border-color: var(--border);
            }

            .card.priority {
                border-left: 3px solid var(--card-priority-border);
                background: var(--card-priority-bg);
            }
            
            .card.representative {
                border-left: 3px solid rgba(79, 172, 254, 0.6);
                background: rgba(79, 172, 254, 0.03);
            }
            
            .sector-subheading {
                font-weight: 600;
                font-size: 0.95rem;
                color: var(--primary);
                margin-top: 24px;
                margin-bottom: 12px;
                padding-left: 8px;
                border-left: 3px solid var(--primary);
            }

            details.related-sources {
                font-size: 0.8rem;
                margin-top: 15px;
                border-top: 1px solid var(--border);
                padding-top: 12px;
            }
            details.related-sources summary {
                color: var(--text-secondary);
                cursor: pointer;
                outline: none;
                list-style: none;
                font-weight: 300;
                display: flex;
                align-items: center;
                gap: 5px;
            }
            .related-link {
                display: block;
                color: var(--primary);
                text-decoration: none;
                padding: 10px 14px;
                margin-top: 8px;
                background: var(--related-bg);
                border-radius: 12px;
                border: 1px solid var(--border);
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
                font-weight: 300;
            }

            .weather-container {
                display: flex;
                align-items: center;
                gap: 20px;
                padding: 15px 35px;
                background: rgba(255, 255, 255, 0.05);
                backdrop-filter: blur(15px);
                border-radius: 40px;
                border: 1px solid rgba(255, 255, 255, 0.1);
                width: fit-content;
                margin: 25px auto 0;
                position: relative;
                z-index: 1;
            }

            #weather-icon-wrapper {
                width: 50px;
                height: 50px;
                display: flex;
                align-items: center;
                justify-content: center;
            }

            #weather-temp-main {
                font-size: 1.4rem;
                font-weight: 700;
                display: flex;
                align-items: center;
                gap: 12px;
                color: #ffffff;
            }

            #weather-range {
                font-size: 0.95rem;
                color: #888;
                font-weight: 400;
            }

            .weather-extra {
                font-size: 0.85rem;
                color: #4facfe;
                margin-top: 4px;
                font-weight: 500;
            }

            #weather-diff-box {
                font-size: 0.85rem;
                color: #ffb74d;
                margin-top: 4px;
                font-weight: 500;
            }

            /* Weather Icons SVGs */
            .weather-svg {
                width: 36px;
                height: 36px;
            }

            .sun {
                fill: #FFD60A;
                animation: rotate 20s linear infinite;
            }

            .cloud {
                fill: #8E8E93;
            }

            .rain-drop {
                fill: #007AFF;
                animation: rain 1s linear infinite;
            }

            .snow-flake {
                fill: #FFFFFF;
                animation: snow 2s linear infinite;
            }

            @keyframes rotate {
                from { transform: rotate(0deg); }
                to { transform: rotate(360deg); }
            }

            @keyframes rain {
                0% { transform: translateY(-5px); opacity: 0; }
                50% { opacity: 1; }
                100% { transform: translateY(10px); opacity: 0; }
            }

            @keyframes snow {
                0% { transform: translateY(-5px) rotate(0deg); opacity: 0; }
                50% { opacity: 1; }
                100% { transform: translateY(10px) rotate(360deg); opacity: 0; }
            }

            footer {
                text-align: center;
                margin-top: 60px;
                color: #333;
                font-size: 0.7rem;
                letter-spacing: 2px;
                text-transform: uppercase;
            }

            /* Push Notification Button */
            .push-subscribe-btn {
                position: relative;
                z-index: 1;
                background: transparent;
                color: var(--text-secondary);
                border: 1px solid var(--border);
                padding: 10px 20px;
                border-radius: 100px;
                font-size: 0.75rem;
                font-weight: 400;
                cursor: pointer;
                margin: 20px auto 0;
                display: block;
                transition: var(--transition);
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            .push-subscribe-btn:hover {
                border-color: var(--primary);
                color: var(--text);
                background: var(--surface);
            }
            .push-subscribe-btn.subscribed {
                opacity: 0.5;
                cursor: default;
            }

        </style>
        """

    def generate_main_page(self, domestic_data, international_data, briefing_data, weather_data, filename, date_str, key_persons=None):
        from datetime import datetime, timezone, timedelta
        kst_now = datetime.now(timezone(timedelta(hours=9)))  # Ensure KST regardless of runner timezone
        gen_time = kst_now.strftime("%H:%M:%S")
        weather_emoji = weather_data.get('emoji', '') if weather_data else ""
        
        # 인물별 섹션에 이미 사용된 기사들의 링크를 추적
        used_article_links = set()
        if key_persons:
            for person_data in key_persons.values():
                for article in person_data.get('articles', []):
                    used_article_links.add(article.get('link'))
        
        html = f"""
        <!DOCTYPE html>
        <html lang="ko">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Morning News {date_str}</title>
            <link rel="manifest" href="manifest.json">
            <script>
              // Service Worker Registration
              if ('serviceWorker' in navigator) {{
                navigator.serviceWorker.register('/sw.js')
                  .then(registration => {{
                    console.log('Service Worker registered:', registration);
                  }})
                  .catch(error => {{
                    console.error('Service Worker registration failed:', error);
                  }});
              }}
              
              // 앱이 다시 활성화될 때 실행
              document.addEventListener("visibilitychange", function() {{
                  if (document.visibilityState === 'visible') {{
                      checkForUpdate();
                  }}
              }});

              function checkForUpdate() {{
                  // 현재 페이지의 'Last-Modified' 헤더를 서버에 요청해서 확인
                  fetch(window.location.href, {{ method: 'HEAD' }})
                      .then(response => {{
                          const serverLastModified = response.headers.get('Last-Modified');
                          const localLastModified = localStorage.getItem('pageLastModified');

                          // 서버의 파일 수정 시간이 저장된 시간과 다르면 새로고침
                          if (serverLastModified && serverLastModified !== localLastModified) {{
                              localStorage.setItem('pageLastModified', serverLastModified);
                              location.reload(true);
                          }}
                      }})
                      .catch(err => console.log('Update check failed:', err));
              }}

              // 처음 로드될 때 현재 페이지의 수정 시간을 저장
              window.onload = function() {{
                  fetch(window.location.href, {{ method: 'HEAD' }})
                      .then(response => {{
                          const lastModified = response.headers.get('Last-Modified');
                          if (lastModified) {{
                              localStorage.setItem('pageLastModified', lastModified);
                          }}
                      }});
              }};
              
              // 알림 권한 요청
              if ("Notification" in window) {{
                  Notification.requestPermission().then(permission => {{
                      if (permission === "granted") {{
                          console.log("알림 권한 허용됨!");
                      }}
                  }});
              }}
              
              // Base64url을 Uint8Array로 변환하는 헬퍼 함수
              function urlBase64ToUint8Array(base64String) {{
                  const padding = '='.repeat((4 - base64String.length % 4) % 4);
                  const base64 = (base64String + padding)
                      .replace(/-/g, '+')
                      .replace(/_/g, '/');
                  const rawData = atob(base64);
                  const outputArray = new Uint8Array(rawData.length);
                  for (let i = 0; i < rawData.length; ++i) {{
                      outputArray[i] = rawData.charCodeAt(i);
                  }}
                  return outputArray;
              }}
              
              // Push 구독 저장 함수
              async function saveSubscription() {{
                  console.log('saveSubscription() 함수 호출됨!');
                  const btn = document.getElementById('subscribeBtn');
                  console.log('버튼 요소:', btn);
                  
                  // Check if Service Worker is supported
                  if (!('serviceWorker' in navigator)) {{
                      console.error('Service Worker 미지원');
                      alert('이 브라우저는 푸시 알림을 지원하지 않습니다.');
                      return;
                  }}
                  console.log('Service Worker 지원 확인');
                  
                  if (!('PushManager' in window)) {{
                      console.error('PushManager 미지원');
                      alert('이 브라우저는 푸시 알림을 지원하지 않습니다.');
                      return;
                  }}
                  console.log('PushManager 지원 확인');
                  
                  // Request notification permission first
                  console.log('현재 알림 권한:', Notification.permission);
                  if (Notification.permission === 'default') {{
                      console.log('알림 권한 요청 중...');
                      const permission = await Notification.requestPermission();
                      console.log('알림 권한 결과:', permission);
                      if (permission !== 'granted') {{
                          alert('알림 권한이 필요합니다. 브라우저 설정에서 알림을 허용해주세요.');
                          return;
                      }}
                  }} else if (Notification.permission === 'denied') {{
                      alert('알림 권한이 거부되었습니다. 브라우저 설정에서 알림을 허용해주세요.');
                      return;
                  }}
                  
                  try {{
                      // Wait for Service Worker to be ready
                      console.log('Service Worker ready 대기 중...');
                      const registration = await navigator.serviceWorker.ready;
                      console.log('Service Worker ready:', registration);
                      
                      // Check if already subscribed
                      console.log('기존 구독 확인 중...');
                      const existingSubscription = await registration.pushManager.getSubscription();
                      console.log('기존 구독:', existingSubscription);
                      if (existingSubscription) {{
                          alert('이미 푸시 알림을 구독하고 있습니다!');
                          if (btn) {{
                              btn.textContent = '✓ 알림 구독 완료';
                              btn.classList.add('subscribed');
                              btn.disabled = true;
                          }}
                          return;
                      }}
                      
                      // VAPID Public Key
                      const VAPID_PUBLIC_KEY = 'BKNrtTTrz1YQEk7x1b6mRtb66K2Oebg7d1a592iVbJ1V2Z4pJefsB28WI8dH6l32tSik2JlWOHuwskDb0IsiVLQ';

                      console.log('VAPID 키로 구독 시작...');
                      const applicationServerKey = urlBase64ToUint8Array(VAPID_PUBLIC_KEY);
                      console.log('변환된 applicationServerKey:', applicationServerKey);
                      
                      // Subscribe to push notifications
                      const subscription = await registration.pushManager.subscribe({{
                          userVisibleOnly: true,
                          applicationServerKey: applicationServerKey
                      }});
                      
                      console.log('Push Subscription 성공:', JSON.stringify(subscription));
                      
                      // Send subscription to server
                      console.log('서버에 구독 정보 전송 중...');
                      // API 서버 주소 - 로컬 테스트용
                      const apiUrl = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
                          ? 'http://localhost:5000/api/save-subscription'
                          : '/api/save-subscription';
                      
                      console.log('API URL:', apiUrl);
                      const response = await fetch(apiUrl, {{
                          method: 'POST',
                          headers: {{ 'Content-Type': 'application/json' }},
                          body: JSON.stringify(subscription)
                      }});
                      
                      console.log('서버 응답 상태:', response.status);
                      const result = await response.json();
                      console.log('Server response:', result);
                      
                      if (response.ok) {{
                          alert('푸시 알림 구독이 완료되었습니다!\\n매일 아침 새로운 뉴스를 알려드립니다.');
                          if (btn) {{
                              btn.textContent = '✓ 알림 구독 완료';
                              btn.classList.add('subscribed');
                              btn.disabled = true;
                          }}
                      }} else {{
                          alert('구독 저장 실패: ' + (result.error || 'Unknown error'));
                      }}
                  }} catch (error) {{
                      console.error('Subscription error:', error);
                      alert('구독 중 오류 발생: ' + error.message + '\\n\\nService Worker가 등록되지 않았을 수 있습니다. 페이지를 새로고침 해보세요.');
                  }}
              }}
              
              // Push 구독 해제 함수
              async function unsubscribePush() {{
                  try {{
                      const registration = await navigator.serviceWorker.ready;
                      const subscription = await registration.pushManager.getSubscription();
                      
                      if (subscription) {{
                          await subscription.unsubscribe();
                          console.log('Push subscription unsubscribed');
                          
                          const btn = document.getElementById('subscribeBtn');
                          if (btn) {{
                              btn.textContent = '🔔 Get Notifications';
                              btn.classList.remove('subscribed');
                              btn.disabled = false;
                          }}
                          
                          alert('푸시 알림 구독이 해제되었습니다.\\n다시 구독하려면 버튼을 눌러주세요.');
                      }} else {{
                          alert('구독 정보가 없습니다.');
                      }}
                  }} catch (error) {{
                      console.error('Unsubscribe error:', error);
                      alert('구독 해제 중 오류 발생: ' + error.message);
                  }}
              }}
              
                document.addEventListener('DOMContentLoaded', async function() {{
                    if ('serviceWorker' in navigator && 'PushManager' in window) {{
                        try {{
                            const registration = await navigator.serviceWorker.ready;
                            const subscription = await registration.pushManager.getSubscription();
                            const btn = document.getElementById('subscribeBtn');
                            
                            if (subscription && btn) {{
                                btn.textContent = '✓ 알림 구독 완료';
                                btn.classList.add('subscribed');
                                btn.disabled = true;
                                
                                // 더블클릭으로 구독 해제 가능하도록
                                btn.ondblclick = unsubscribePush;
                            }}
                        }} catch (error) {{
                            console.error('Error checking subscription:', error);
                        }}
                    }}
                }});

                // --- Animated Weather Logic ---
                const weatherIcons = {{
                    sunny: `<svg class="weather-svg" viewBox="0 0 64 64"><circle class="sun" cx="32" cy="32" r="12"/><g stroke="#FFD60A" stroke-width="2"><line x1="32" y1="8" x2="32" y2="14"/><line x1="32" y1="50" x2="32" y2="56"/><line x1="8" y1="32" x2="14" y2="32"/><line x1="50" y1="32" x2="56" y2="32"/><line x1="15" y1="15" x2="19" y2="19"/><line x1="45" y1="45" x2="49" y2="49"/><line x1="15" y1="49" x2="19" y2="45"/><line x1="45" y1="19" x2="49" y2="15"/></g></svg>`,
                    cloudy: `<svg class="weather-svg" viewBox="0 0 64 64"><path class="cloud" d="M46,38c0,4.4-3.6,8-8,8H24c-5.5,0-10-4.5-10-10c0-4.8,3.4-8.9,8-9.8c1.1-4.7,5.3-8.2,10-8.2c4,0,7.5,2.3,9.2,5.7C43.5,24.6,46,28,46,32v6z"/></svg>`,
                    rainy: `<svg class="weather-svg" viewBox="0 0 64 64"><path class="cloud" d="M46,32c0,4.4-3.6,8-8,8H24c-5.5,0-10-4.5-10-10c0-4.8,3.4-8.9,8-9.8c1.1-4.7,5.3-8.2,10-8.2c4,0,7.5,2.3,9.2,5.7C43.5,24.6,46,28,46,32v6z"/><circle class="rain-drop" cx="24" cy="50" r="1.5"/><circle class="rain-drop" cx="32" cy="54" r="1.5"/><circle class="rain-drop" cx="40" cy="50" r="1.5"/></svg>`,
                    snowy: `<svg class="weather-svg" viewBox="0 0 64 64"><path class="cloud" d="M46,32c0,4.4-3.6,8-8,8H24c-5.5,0-10-4.5-10-10c0-4.8,3.4-8.9,8-9.8c1.1-4.7,5.3-8.2,10-8.2c4,0,7.5,2.3,9.2,5.7C43.5,24.6,46,28,46,32v6z"/><circle class="snow-flake" cx="24" cy="52" r="2"/><circle class="snow-flake" cx="32" cy="56" r="2"/><circle class="snow-flake" cx="40" cy="52" r="2"/></svg>`,
                    stormy: `<svg class="weather-svg" viewBox="0 0 64 64"><path class="cloud" d="M46,32c0,4.4-3.6,8-8,8H24c-5.5,0-10-4.5-10-10c0-4.8,3.4-8.9,8-9.8c1.1-4.7,5.3-8.2,10-8.2c4,0,7.5,2.3,9.2,5.7C43.5,24.6,46,28,46,32v6z"/><polygon fill="#FFD60A" points="30,44 24,54 34,54 30,64 40,52 30,52" /></svg>`
                }};

                async function updateWeather() {{
                    try {{
                        const lat = 37.68;
                        const lon = 126.82;
                        const url = `https://api.open-meteo.com/v1/forecast?latitude=${{lat}}&longitude=${{lon}}&current=temperature_2m,weather_code&hourly=temperature_2m,precipitation_probability&daily=temperature_2m_max,temperature_2m_min&timezone=Asia%2FSeoul&past_days=1`;

                        const res = await fetch(url);
                        const data = await res.json();

                        const temp = Math.round(data.current.temperature_2m);
                        const max = Math.round(data.daily.temperature_2m_max[1]);
                        const min = Math.round(data.daily.temperature_2m_min[1]);
                        const code = data.current.weather_code;
                        
                        const curHour = new Date().getHours();
                        const currIdx = 24 + curHour;
                        const rainProb = data.hourly.precipitation_probability[currIdx] || 0;

                        document.getElementById('temp-val').textContent = `${{temp}}°`;
                        document.getElementById('weather-range').textContent = `${{min}}° / ${{max}}°`;
                        document.getElementById('weather-desc').textContent = `강수 확률: ${{rainProb}}%`;

                        // 어제 동일 시간 기온과 실시간 비교
                        try {{
                            const yesterdayTemp = data.hourly.temperature_2m[currIdx - 24];
                            const diff = (data.current.temperature_2m - yesterdayTemp).toFixed(1);
                            let diffMsg = "";
                            const absDiff = Math.abs(diff);
                            if (diff > 0) diffMsg = `어제보다 ${{absDiff}}° 높습니다`;
                            else if (diff < 0) diffMsg = `어제보다 ${{absDiff}}° 낮습니다`;
                            else diffMsg = "어제와 기온이 같습니다";
                            
                            const diffElement = document.getElementById('weather-diff-box');
                            if (diffElement) diffElement.textContent = diffMsg;
                        }} catch (err) {{
                            console.error('Diff calculation error:', err);
                        }}

                        let icon = weatherIcons.sunny;
                        if ([1, 2, 3, 45, 48].includes(code)) icon = weatherIcons.cloudy;
                        else if ([51, 53, 55, 61, 63, 65, 80, 81, 82].includes(code)) icon = weatherIcons.rainy;
                        else if ([71, 73, 75, 77, 85, 86].includes(code)) icon = weatherIcons.snowy;
                        else if ([95, 96, 99].includes(code)) icon = weatherIcons.stormy;

                        document.getElementById('weather-icon-wrapper').innerHTML = icon;
                    }} catch (e) {{
                        console.error('Weather update failed:', e);
                    }}
                }}

                updateWeather();
                setInterval(updateWeather, 1800000);
            </script>
            {self.css}
        </head>
        <body>
            <div class="container">
                <header>
                    <div class="header-meta">
                        <span class="header-date">{date_str}</span>
                        <span class="header-time">Generated at {gen_time}</span>
                    </div>
                    <h1>Morning News</h1>
                    {self._generate_weather_html(weather_data)}
                    <button id="subscribeBtn" class="push-subscribe-btn" onclick="saveSubscription()">🔔 Get Notifications</button>
                </header>
        """
        

        # --- Generate Sticky Nav ---
        order = ["정치", "경제/거시", "기업/산업", "부동산", "국제"]
        
        html += '<div class="sticky-nav">'
        html += '<a href="https://gemini-783885185452.us-west1.run.app/" class="nav-pill" target="_blank" rel="noopener noreferrer">🔎 Gemini 네비게이터</a>'
        
        # Key Persons (if exists)
        if key_persons:
            person_count = sum(p['count'] for p in key_persons.values())
            html += f'<a href="#인물별" class="nav-pill">👤 인물별 ({person_count})</a>'
        
        # Domestic Counts (필터링 후 개수)
        for category in order:
            items = domestic_data.get(category, [])
            filtered_items = [item for item in items if item.get('link') not in used_article_links]
            count = len(filtered_items)
            if count > 0:
                html += f'<a href="#{category}" class="nav-pill">{category} ({count})</a>'
        
        # Science Times Count
        science_count = len(international_data)
        if science_count > 0:
            html += f'<a href="#science" class="nav-pill">테크 ({science_count})</a>'
            
        html += '</div>'
        
        # Render Briefing
        if briefing_data:
            html += '<div class="briefing-card">'
            html += '<div class="briefing-title">⚡ Morning Briefing</div>'
            
            # Summaries
            summaries = briefing_data.get('section_summaries', {})
            for section, summary in summaries.items():
                if summary:
                    html += f"""
                    <div class="briefing-item">
                        <span class="briefing-label">{section}</span>
                        <span class="briefing-content">{summary}</span>
                    </div>
                    """
            
            # Sentiment (Companies)
            hojae = briefing_data.get('hojae', [])
            akjae = briefing_data.get('akjae', [])
            
            if hojae or akjae:
                html += '<div class="sentiment-box">'
                if hojae:
                    html += '<div class="sentiment-row"><span class="sentiment-type hojae">📈 호재</span> <div class="sentiment-items">'
                    for item in hojae:
                        html += f'<div class="sentiment-item">{item}</div>'
                    html += '</div></div>'
                
                if akjae:
                    html += '<div class="sentiment-row"><span class="sentiment-type akjae">📉 악재</span> <div class="sentiment-items">'
                    for item in akjae:
                        html += f'<div class="sentiment-item">{item}</div>'
                    html += '</div></div>'
                html += '</div>'
                
            html += '</div>'


        # Key Persons Section (if exists)
        if key_persons:
            html += '<div id="인물별" class="section-title">🔍 주요 인물별 뉴스</div>'
            
            for person_name, person_data in key_persons.items():
                role = person_data.get('role', '')
                articles = person_data.get('articles', [])
                count = person_data.get('count', len(articles))
                
                # Person subheading
                role_text = f" ({role})" if role else ""
                html += f'<div class="sector-subheading">👤 {person_name}{role_text} ({count}건)</div>'
                
                # Render articles
                for item in articles:
                    # datetime 객체인지 확인하고 문자열이면 변환
                    if isinstance(item['published_dt'], str):
                        try:
                            from datetime import datetime
                            time_str = datetime.fromisoformat(item['published_dt']).strftime("%m.%d %H:%M")
                        except:
                            time_str = item['published_dt']
                    else:
                        time_str = item['published_dt'].strftime("%m.%d %H:%M")
                    
                    html += f"""
                <div class="card">
                    <a href="{item['link']}" class="card-title" target="_blank" style="text-decoration: none; color: inherit; display: block;">{item['title']}</a>
                    <div class="card-meta">
                        <span>{item['source']}</span>
                        <span>{time_str}</span>
                    </div>
                </div>
                """


        # Domestic Sections
        order = ["정치", "경제/거시", "기업/산업", "부동산", "국제"]
        for category in order:
            items = domestic_data.get(category, [])
            if not items:
                continue
            
            # 인물별 섹션에 이미 사용된 기사는 제외
            filtered_items = [item for item in items if item.get('link') not in used_article_links]
            if not filtered_items:
                continue
            
            # 기업/산업은 섹터별, 정치는 세부 분류별로 그룹화
            if category in ("기업/산업", "정치"):
                html += f'<div id="{category}" class="section-title">{category}</div>'

                if category == "기업/산업":
                    # 섹터별로 분류
                    buckets = {}
                    for item in filtered_items:
                        key = item.get('sector', '기타산업')
                        buckets.setdefault(key, []).append(item)
                    order_keys = ["AI/로봇", "반도체", "자동차", "배터리/에너지", "바이오/제약", "조선해양", "금융", 
                                  "통신/IT", "유통/소매", "건설", "화학/소재", "기타산업"]
                    icon = "📌"
                else:
                    # 정치 세부 분류
                    buckets = {}
                    for item in filtered_items:
                        key = item.get('pol_subcategory', '기타')
                        buckets.setdefault(key, []).append(item)
                    order_keys = ["정상/외교", "당내 정국", "사법/의혹", "지방/행정", "입법/정책", "Science/Tech", "기타"]
                    icon = "🗂️"

                for key in order_keys:
                    if key not in buckets:
                        continue
                    group_items = buckets[key]
                    
                    # 정치 카테고리인 경우 대표 기사를 맨 앞으로 정렬
                    if category == "정치":
                        group_items.sort(key=lambda x: (not x.get('is_representative', False), -x['published_dt'].timestamp()))
                    
                    html += f'<div class="sector-subheading">{icon} {key} ({len(group_items)})</div>'

                    for item in group_items:
                        time_str = item['published_dt'].strftime("%m.%d %H:%M")
                        priority_class = "priority" if item.get('priority_score', 0) > 0 else ""
                        
                        # 대표 기사 표시
                        representative_badge = ""
                        if category == "정치" and item.get('is_representative', False):
                            priority_class += " representative"

                        # Grouped sources detail with count
                        related_info = ""
                        related_sources = item.get('related_full_sources', [])
                        if related_sources:
                            count_badge = f" (외 {len(related_sources)}건)"
                            links_html = "".join([f'<a href="{rs["link"]}" class="related-link" target="_blank">🔗 {rs["title"]} - {rs["source"]}</a>' for rs in related_sources])
                            related_info = f"""
                        <details class="related-sources">
                            <summary>{len(related_sources)}개 관련 기사 보기</summary>
                            {links_html}
                        </details>
                        """
                        else:
                            count_badge = ""

                        html += f"""
                    <div class="card {priority_class}">
                        <a href="{item['link']}" class="card-title" target="_blank" style="text-decoration: none; color: inherit; display: block;">{item['title']}{count_badge}{representative_badge}</a>
                        <div class="card-meta">
                            <span>{item['source']}</span>
                            <span>{time_str}</span>
                        </div>
                        {related_info}
                    </div>
                    """
            else:
                # 다른 카테고리는 기존처럼 처리
                html += f'<div id="{category}" class="section-title">{category}</div>'
                for item in filtered_items:
                    time_str = item['published_dt'].strftime("%m.%d %H:%M")
                    priority_class = "priority" if item.get('priority_score', 0) > 0 else ""
                    
                    # Grouped sources detail
                    related_info = ""
                    related_sources = item.get('related_full_sources', [])
                    if related_sources:
                        links_html = "".join([f'<a href="{rs["link"]}" class="related-link" target="_blank">🔗 {rs["title"]} - {rs["source"]}</a>' for rs in related_sources])
                        related_info = f"""
                    <details class="related-sources">
                        <summary>Explore {len(related_sources)} more sources</summary>
                        {links_html}
                    </details>
                    """

                    html += f"""
                <div class="card {priority_class}">
                    <a href="{item['link']}" class="card-title" target="_blank" style="text-decoration: none; color: inherit; display: block;">{item['title']}</a>
                    <div class="card-meta">
                        <span>{item['source']}</span>
                        <span>{time_str}</span>
                    </div>
                    {related_info}
                </div>
                """

        if international_data:
            html += f'<div id="science" class="section-title">테크</div>'
            for item in international_data:
                time_str = item['published_dt'].strftime("%m.%d %H:%M")
                html += f"""
                <a href="{item['link']}" class="card" target="_blank">
                    <div class="card-title">{item['title']}</div>
                    <div class="card-meta">
                        <span>사이언스타임즈</span>
                        <span>{time_str}</span>
                    </div>
                </a>
                """

        html += """
                <footer>&copy; 2025 PREMIUM MORNING NEWS BOT</footer>
            </div>
            <div class="sticky-nav">

            # Gemini navigator shortcut (opens in new tab)
            html += '<a href="https://gemini-783885185452.us-west1.run.app/" class="nav-pill" target="_blank" rel="noopener noreferrer">🔎 Gemini 네비게이터</a>'
        </html>
        """
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html)
            
        print(f"Generated {filename}")

    def _generate_weather_html(self, weather_data):
        if not weather_data:
            return ""
        
        diff_msg = weather_data.get('diff_msg', '')
        # dashboard.html과 동일하게 weather-diff div를 추가, diff_msg가 있으면 기본값으로 출력
        return f"""
        <div class="weather-container">
            <div id="weather-icon-wrapper">
                <!-- Dynamic SVG Icon -->
            </div>
            <div class="weather-details">
                <div id="weather-temp-main">
                    <span id="temp-val">--°</span>
                    <span id="weather-range">--° / --°</span>
                </div>
                <div class="weather-extra" id="weather-desc">LOADING...</div>
                <div class="weather-diff-box" id="weather-diff-box">{diff_msg}</div>
            </div>
        </div>
        """

    def generate_detail_page(self, article, filename):
        # Disabled as per user request to move away from sub-pages
        pass
