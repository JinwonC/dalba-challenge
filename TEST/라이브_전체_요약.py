"""라이브 전체 요약 → Google Sheets '라이브_전체_요약' 탭"""
from _공통 import call_api, get_sheet, write_to_sheet, get_date_input

SHEET_NAME = "라이브_전체_요약"
PATH = "/analytics/202309/lives/overview"

HEADERS = ["날짜", "총라이브수", "총시청자수", "총주문수", "총GMV", "평균시청시간"]

def run(date_str: str):
    print(f"\n=== 라이브 전체 요약 [{date_str}] ===")
    sheet = get_sheet(SHEET_NAME)

    result = call_api(PATH, {
        "start_date": date_str,
        "end_date": date_str,
    })

    if not result:
        print("  API 호출 실패")
        return

    data = result.get("data") or {}
    row = [
        date_str,
        data.get("total_lives") or data.get("live_count") or "",
        data.get("total_viewers") or data.get("viewers") or "",
        data.get("total_orders") or data.get("orders") or "",
        data.get("total_gmv") or data.get("gmv") or "",
        data.get("avg_watch_duration") or "",
    ]
    write_to_sheet(sheet, HEADERS, [row])

if __name__ == "__main__":
    run(get_date_input())
