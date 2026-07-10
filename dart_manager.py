import os
from datetime import datetime, timedelta, timezone

import requests

from rss_manager import enrich_news_item


IMPORTANT_REPORT_HINTS = [
    "주요사항보고서",
    "단일판매",
    "공급계약",
    "신규시설투자",
    "자기주식",
    "유상증자",
    "무상증자",
    "전환사채",
    "신주인수권",
    "최대주주",
    "영업정지",
    "회생절차",
    "소송",
    "잠정실적",
    "영업실적",
    "배당",
    "합병",
    "분할",
    "상장폐지",
]


class DARTManager:
    """Optional OpenDART disclosure collector.

    Enabled only when OPEN_DART_API_KEY or DART_API_KEY is present.  Returned
    items intentionally match the RSS news item shape so the existing AI
    categorization pipeline can consume disclosures without special handling.
    """

    BASE_URL = "https://opendart.fss.or.kr/api/list.json"

    def __init__(self):
        self.api_key = os.getenv("OPEN_DART_API_KEY") or os.getenv("DART_API_KEY")

    def is_enabled(self) -> bool:
        return bool(self.api_key)

    @staticmethod
    def _is_important_report(report_name: str) -> bool:
        text = report_name or ""
        return any(hint in text for hint in IMPORTANT_REPORT_HINTS)

    @staticmethod
    def _parse_receipt_datetime(receipt_no: str, fallback_date: str):
        # rcept_no begins with YYYYMMDD in OpenDART.
        raw_date = (receipt_no or "")[:8] if receipt_no else fallback_date
        try:
            return datetime.strptime(raw_date, "%Y%m%d").replace(hour=8, minute=30)
        except Exception:
            return datetime.now(timezone(timedelta(hours=9))).replace(tzinfo=None)

    def fetch_disclosures(self, *, days: int = 1, max_items: int = 80) -> list[dict]:
        if not self.is_enabled():
            print("ℹ️ OpenDART API 키가 없어 DART 공시 수집을 건너뜁니다.")
            return []

        kst = timezone(timedelta(hours=9))
        now = datetime.now(kst)
        begin = (now - timedelta(days=days)).strftime("%Y%m%d")
        end = now.strftime("%Y%m%d")

        params = {
            "crtfc_key": self.api_key,
            "bgn_de": begin,
            "end_de": end,
            "page_count": "100",
            "page_no": "1",
            "sort": "date",
            "sort_mth": "desc",
        }

        try:
            res = requests.get(self.BASE_URL, params=params, timeout=20)
            res.raise_for_status()
            payload = res.json()
        except Exception as e:
            print(f"⚠️ DART 공시 수집 실패: {e}")
            return []

        if payload.get("status") not in {"000", "013"}:
            print(f"⚠️ DART API 응답 오류: {payload.get('status')} {payload.get('message')}")
            return []

        rows = payload.get("list") or []
        items: list[dict] = []
        for row in rows:
            report_name = row.get("report_nm", "")
            if not self._is_important_report(report_name):
                continue

            corp_name = row.get("corp_name", "")
            receipt_no = row.get("rcept_no", "")
            receipt_date = row.get("rcept_dt", end)
            title = f"[DART] {corp_name}: {report_name}".strip()
            link = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt_no}" if receipt_no else "https://dart.fss.or.kr/"
            description = f"{corp_name} 공시 - {report_name} / 접수일 {receipt_date}"
            item = {
                "title": title,
                "link": link,
                "source": "DART",
                "published_dt": self._parse_receipt_datetime(receipt_no, receipt_date),
                "description": description,
                "category": "domestic",
                "source_type": "disclosure",
            }
            items.append(enrich_news_item(item, source_type="disclosure"))
            if len(items) >= max_items:
                break

        print(f"  - DART important disclosures: {len(items)}")
        return items
