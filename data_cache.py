import json
import os
from datetime import datetime
from config import config

class DataCache:
    def __init__(self):
        self.cache_dir = "data_cache"
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def get_cache_filename(self, cache_type, date_str=None):
        """
        캐시 파일명 생성
        cache_type: 'rss', 'ai_analysis', 'key_persons', 'trending_keywords'
        """
        if date_str is None:
            date_str = datetime.now().strftime("%Y%m%d")
        return os.path.join(self.cache_dir, f"{cache_type}_{date_str}.json")
    
    def save_rss_data(self, rss_data, date_str=None):
        """RSS 수집 데이터 캐시 저장"""
        cache_file = self.get_cache_filename('rss', date_str)
        tmp_file = f"{cache_file}.tmp"
        try:
            cache_data = {
                "timestamp": datetime.now().isoformat(),
                "date": date_str or datetime.now().strftime("%Y%m%d"),
                "data": rss_data
            }
            with open(tmp_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2, default=str)
            os.replace(tmp_file, cache_file)
            print(f"✅ RSS 데이터 캐시 저장: {cache_file}")
            return True
        except Exception as e:
            if os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except Exception:
                    pass
            print(f"❌ RSS 캐시 저장 실패: {e}")
            return False
    
    def load_rss_data(self, date_str=None):
        """RSS 수집 데이터 캐시 로드"""
        cache_file = self.get_cache_filename('rss', date_str)
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                print(f"✅ RSS 데이터 캐시 로드: {cache_file}")
                loaded_data = cache_data.get("data", [])
                # datetime 객체 복원
                for item in loaded_data:
                    if 'published_dt' in item and isinstance(item['published_dt'], str):
                        item['published_dt'] = datetime.fromisoformat(item['published_dt'])
                return loaded_data
            except Exception as e:
                print(f"❌ RSS 캐시 로드 실패: {e}")
        return None
    
    def save_ai_analysis(self, ai_data, date_str=None):
        """AI 분석 데이터 캐시 저장"""
        cache_file = self.get_cache_filename('ai_analysis', date_str)
        tmp_file = f"{cache_file}.tmp"
        try:
            cache_data = {
                "timestamp": datetime.now().isoformat(),
                "date": date_str or datetime.now().strftime("%Y%m%d"),
                "data": ai_data
            }
            with open(tmp_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2, default=str)
            os.replace(tmp_file, cache_file)
            print(f"✅ AI 분석 데이터 캐시 저장: {cache_file}")
            return True
        except Exception as e:
            if os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except Exception:
                    pass
            print(f"❌ AI 분석 캐시 저장 실패: {e}")
            return False
    
    def load_ai_analysis(self, date_str=None):
        """AI 분석 데이터 캐시 로드"""
        cache_file = self.get_cache_filename('ai_analysis', date_str)
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                print(f"✅ AI 분석 데이터 캐시 로드: {cache_file}")
                loaded_data = cache_data.get("data", {})
                # datetime 객체 복원
                for category, items in loaded_data.items():
                    for item in items:
                        if 'published_dt' in item and isinstance(item['published_dt'], str):
                            item['published_dt'] = datetime.fromisoformat(item['published_dt'])
                return loaded_data
            except Exception as e:
                print(f"❌ AI 분석 캐시 로드 실패: {e}")
        return None
    
    def save_key_persons(self, key_persons, date_str=None):
        """주요 인물 추출 데이터 캐시 저장"""
        cache_file = self.get_cache_filename('key_persons', date_str)
        tmp_file = f"{cache_file}.tmp"
        try:
            cache_data = {
                "timestamp": datetime.now().isoformat(),
                "date": date_str or datetime.now().strftime("%Y%m%d"),
                "data": key_persons
            }
            with open(tmp_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2, default=str)
            os.replace(tmp_file, cache_file)
            print(f"✅ 주요 인물 데이터 캐시 저장: {cache_file}")
            return True
        except Exception as e:
            if os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except Exception:
                    pass
            print(f"❌ 주요 인물 캐시 저장 실패: {e}")
            return False
    
    def load_key_persons(self, date_str=None):
        """주요 인물 추출 데이터 캐시 로드"""
        cache_file = self.get_cache_filename('key_persons', date_str)
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                print(f"✅ 주요 인물 데이터 캐시 로드: {cache_file}")
                return cache_data.get("data", {})
            except Exception as e:
                print(f"❌ 주요 인물 캐시 로드 실패: {e}")
        return None

    def save_trending_keywords(self, keywords, date_str=None):
        """오늘의 키워드 TOP10 캐시 저장"""
        cache_file = self.get_cache_filename('trending_keywords', date_str)
        tmp_file = f"{cache_file}.tmp"
        try:
            cache_data = {
                "timestamp": datetime.now().isoformat(),
                "date": date_str or datetime.now().strftime("%Y%m%d"),
                "data": keywords
            }
            with open(tmp_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2, default=str)
            os.replace(tmp_file, cache_file)
            print(f"✅ 오늘의 키워드 데이터 캐시 저장: {cache_file}")
            return True
        except Exception as e:
            if os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except Exception:
                    pass
            print(f"❌ 오늘의 키워드 캐시 저장 실패: {e}")
            return False

    def load_trending_keywords(self, date_str=None):
        """오늘의 키워드 TOP10 캐시 로드"""
        cache_file = self.get_cache_filename('trending_keywords', date_str)
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                print(f"✅ 오늘의 키워드 데이터 캐시 로드: {cache_file}")
                return cache_data.get("data", [])
            except Exception as e:
                print(f"❌ 오늘의 키워드 캐시 로드 실패: {e}")
        return None
    
    def has_cache(self, cache_type, date_str=None):
        """특정 타입의 캐시가 존재하는지 확인"""
        cache_file = self.get_cache_filename(cache_type, date_str)
        return os.path.exists(cache_file)
    
    def get_cache_status(self, date_str=None):
        """오늘의 캐시 상태 확인"""
        if date_str is None:
            date_str = datetime.now().strftime("%Y%m%d")
        
        status = {
            "date": date_str,
            "rss": self.has_cache('rss', date_str),
            "ai_analysis": self.has_cache('ai_analysis', date_str),
            "key_persons": self.has_cache('key_persons', date_str),
            "trending_keywords": self.has_cache('trending_keywords', date_str),
            "all_complete": False
        }
        
        status["all_complete"] = all([
            status["rss"],
            status["ai_analysis"], 
            status["key_persons"],
            status["trending_keywords"]
        ])
        
        return status
    
    def clear_cache(self, cache_type=None, date_str=None):
        """캐시 파일 정리"""
        if cache_type:
            # 특정 타입만 정리
            cache_file = self.get_cache_filename(cache_type, date_str)
            if os.path.exists(cache_file):
                try:
                    os.remove(cache_file)
                    print(f"🗑️ 캐시 파일 정리: {cache_file}")
                    return True
                except Exception as e:
                    print(f"❌ 캐시 파일 정리 실패: {e}")
        else:
            # 모든 캐시 정리
            if date_str is None:
                date_str = datetime.now().strftime("%Y%m%d")
            
            for cache_type in ['rss', 'ai_analysis', 'key_persons', 'trending_keywords']:
                self.clear_cache(cache_type, date_str)
        
        return False
    
    def list_cache_files(self):
        """캐시 파일 목록 확인"""
        cache_files = []
        if os.path.exists(self.cache_dir):
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.json'):
                    filepath = os.path.join(self.cache_dir, filename)
                    file_info = {
                        "filename": filename,
                        "filepath": filepath,
                        "size": os.path.getsize(filepath),
                        "modified": datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat()
                    }
                    cache_files.append(file_info)
        
        return sorted(cache_files, key=lambda x: x["modified"], reverse=True)

if __name__ == "__main__":
    # DataCache 테스트
    cache = DataCache()
    
    print("🧪 DataCache 테스트 시작...")
    
    # 테스트 데이터
    test_rss = [
        {"title": "테스트 뉴스 1", "source": "테스트", "published_dt": "2026-01-17"},
        {"title": "테스트 뉴스 2", "source": "테스트", "published_dt": "2026-01-17"}
    ]
    
    test_ai = {
        "정치": [{"title": "테스트 정치", "source": "테스트"}],
        "경제/거시": [{"title": "테스트 경제", "source": "테스트"}]
    }
    
    test_persons = {
        "테스트 인물": {"articles": [], "count": 5, "role": "테스트 역할"}
    }
    
    # 저장 테스트
    cache.save_rss_data(test_rss)
    cache.save_ai_analysis(test_ai)
    cache.save_key_persons(test_persons)
    
    # 로드 테스트
    loaded_rss = cache.load_rss_data()
    loaded_ai = cache.load_ai_analysis()
    loaded_persons = cache.load_key_persons()
    
    print(f"✅ RSS 로드: {'성공' if loaded_rss else '실패'}")
    print(f"✅ AI 분석 로드: {'성공' if loaded_ai else '실패'}")
    print(f"✅ 주요 인물 로드: {'성공' if loaded_persons else '실패'}")
    
    # 상태 확인
    status = cache.get_cache_status()
    print(f"📊 캐시 상태: {status}")
    
    # 파일 목록
    files = cache.list_cache_files()
    print(f"📁 캐시 파일: {len(files)}개")
    
    print("🎉 DataCache 테스트 완료!")
