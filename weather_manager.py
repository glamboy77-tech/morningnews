import os
import requests
from datetime import datetime
from dotenv import load_dotenv
from config import config

load_dotenv()

class WeatherManager:
    def __init__(self):
        self.last_temp_file = "last_temp.txt"
        
        # 지역별 좌표 매핑
        self.location_coords = {
            "일산": {"lat": 37.68, "lon": 126.82, "name": "식사동"},
            "서울": {"lat": 37.5665, "lon": 126.9780, "name": "서울"},
            "부산": {"lat": 35.1796, "lon": 129.0756, "name": "부산"},
            "인천": {"lat": 37.4563, "lon": 126.7052, "name": "인천"},
            "대전": {"lat": 36.3504, "lon": 127.3845, "name": "대전"},
            "대구": {"lat": 35.8714, "lon": 128.6014, "name": "대구"},
            "광주": {"lat": 35.1595, "lon": 126.8526, "name": "광주"},
        }

    def get_weather(self):
        try:
            # 환경 변수에서 위치 가져오기 (기본값: 일산)
            location_key = config.weather_location
            location_info = self.location_coords.get(location_key, self.location_coords["일산"])
            
            lat = location_info["lat"]
            lon = location_info["lon"]
            location_name = location_info["name"]
            
            # Open-Meteo API
            # past_days=1을 추가하여 어제 데이터도 함께 가져옵니다.
            url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,weather_code&hourly=temperature_2m&daily=temperature_2m_max,temperature_2m_min&timezone=Asia%2FSeoul&past_days=1"

            res = requests.get(url)
            data = res.json()

            current_temp = data['current']['temperature_2m']
            max_temp = data['daily']['temperature_2m_max'][1] # [0]은 어제, [1]은 오늘
            min_temp = data['daily']['temperature_2m_min'][1]
            
            # 어제 같은 시간대 기온 추출
            # hourly 데이터에서 현재 시간으로부터 24시간 전 데이터를 찾습니다.
            current_time_str = data['current']['time']
            current_time_dt = datetime.fromisoformat(current_time_str)
            
            # hourly.time 리스트에서 어제 같은 시간을 찾기 위해 인덱스 계산
            # current 데이터의 시간 인덱스를 찾고 거기서 24를 뺍니다.
            times = data['hourly']['time']
            temps = data['hourly']['temperature_2m']
            
            try:
                # API 응답의 hourly 데이터는 어제 00:00부터 시작하므로 
                # 현재 시간의 인덱스를 찾은 후 24를 빼면 어제 같은 시간이 됩니다.
                curr_idx = times.index(current_time_str)
                yesterday_temp = temps[curr_idx - 24]
                diff = float(current_temp) - yesterday_temp
                abs_diff = round(abs(diff), 1)
                if diff > 0:
                    diff_msg = f"어제보다 {abs_diff}° 높습니다"
                elif diff < 0:
                    diff_msg = f"어제보다 {abs_diff}° 낮습니다"
                else:
                    diff_msg = "어제와 기온이 같습니다"
            except (ValueError, IndexError):
                diff_msg = ""

            return {
                "location": location_name,
                "max_temp": f"{max_temp:g}",
                "min_temp": f"{min_temp:g}",
                "current_temp": f"{current_temp:g}",
                "diff_msg": diff_msg,
                "emoji": "🌡️", 
                "desc": "실시간 기상 데이터"
            }

        except Exception as e:
            print(f"Weather Error: {e}")
            return None

if __name__ == "__main__":
    wm = WeatherManager()
    print(wm.get_weather())