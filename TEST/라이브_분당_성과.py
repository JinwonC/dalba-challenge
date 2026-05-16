"""라이브 분당 성과 → Google Sheets '라이브_분당_성과' 탭
먼저 해당 날짜의 라이브 목록을 가져온 후, 각 라이브의 분당 데이터를 수집합니다.
"""
from _공통 import call_api, get_sheet, write_to_sheet, get_date_input

SHEET_NAME = "라이브_분당_성과"
LIST_PATH = "/analytics/202309/lives/performance"
DETAIL_PATH = "/analytics/202309/lives/performance/minutely"

HEADERS = ["날짜", "라이브ID", "분(timestamp)", "동시시청자수", "누적시청자수", "좋아요수"]

def run(date_str: str):
    print(f"\n=== 라이브 분당 성과 [{date_str}] ===")
    sheet = get_sheet(SHEET_NAME)

    # 1. 라이브 목록 조회
    result = call_api(LIST_PATH, {
        "start_date": date_str,
        "end_date": date_str,
        "page_size": "100",
    })
    if not result:
        print("  라이브 목록 조회 실패")
        return

    data = result.get("data") or {}
    lives = data.get("lives") or data.get("list") or []

    if not lives:
        print("  해당 날짜 라이브 없음")
        return

    all_rows = []
    for live in lives:
        live_id = live.get("live_id") or live.get("id") or ""
        if not live_id:
            continue

        print(f"  라이브 [{live_id}] 분당 데이터 수집 중...")
        detail = call_api(DETAIL_PATH, {"live_id": live_id})
        if not detail:
            continue

        items = detail.get("data") or []
        if isinstance(items, dict):
            items = items.get("list") or items.get("minutely") or []

        for item in items:
            all_rows.append([
                date_str,
                live_id,
                item.get("minute") or item.get("timestamp") or "",
                item.get("concurrent_viewers") or item.get("peak_viewers") or "",
                item.get("total_viewers") or "",
                item.get("likes") or "",
            ])

    write_to_sheet(sheet, HEADERS, all_rows)

if __name__ == "__main__":
    run(get_date_input())
