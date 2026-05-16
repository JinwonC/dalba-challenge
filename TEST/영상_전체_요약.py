"""영상 전체 요약 → Google Sheets '영상_전체_요약' 탭"""
from _공통 import call_api, get_sheet, write_to_sheet, get_date_input
from datetime import datetime, timedelta

SHEET_NAME = "영상_전체_요약"
PATH = "/analytics/202509/shop_videos/overview_performance"

HEADERS = ["날짜", "총조회수", "총GMV", "통화", "총주문수", "총판매수량", "평균CTR", "평균GPM"]

def run(date_str: str):
    print(f"\n=== 영상 전체 요약 [{date_str}] ===")
    sheet = get_sheet(SHEET_NAME)

    next_day = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

    result = call_api(PATH, {
        "start_date_ge": date_str,
        "end_date_lt": next_day,
        "granularity": "ALL",
        "currency": "USD",
        "account_type": "ALL",
    })

    if not result:
        print("  API 호출 실패")
        return

    data = result.get("data") or {}
    metrics = data.get("metrics") or data
    gmv = metrics.get("gmv") or {}

    row = [
        date_str,
        metrics.get("video_play_count") or metrics.get("views") or "",
        gmv.get("amount") if isinstance(gmv, dict) else gmv or "",
        gmv.get("currency") if isinstance(gmv, dict) else "USD",
        metrics.get("order_count") or metrics.get("orders") or "",
        metrics.get("item_sold_count") or metrics.get("units_sold") or "",
        metrics.get("click_through_rate") or metrics.get("ctr") or "",
        metrics.get("gpm") or "",
    ]
    write_to_sheet(sheet, HEADERS, [row])

if __name__ == "__main__":
    run(get_date_input())
