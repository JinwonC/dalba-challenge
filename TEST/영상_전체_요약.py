"""영상 전체 요약 → Google Sheets '영상_전체_요약' 탭"""
from _공통 import call_api, get_sheet, write_to_sheet, get_date_input
from datetime import datetime, timedelta

SHEET_NAME = "영상_전체_요약"
PATH = "/analytics/202509/shop_videos/overview_performance"

HEADERS = ["날짜(시작)", "날짜(종료)", "평균구매고객수", "CTR", "GMV", "통화", "상품클릭수", "상품노출수", "SKU주문수"]

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

    intervals = (result.get("data") or {}).get("performance", {}).get("intervals") or []
    rows = []
    for item in intervals:
        gmv = item.get("gmv") or {}
        rows.append([
            item.get("start_date") or date_str,
            item.get("end_date") or "",
            item.get("avg_customers") or "",
            item.get("click_through_rate") or "",
            gmv.get("amount") or "",
            gmv.get("currency") or "USD",
            item.get("product_clicks") or "",
            item.get("product_impressions") or "",
            item.get("sku_orders") or "",
        ])

    write_to_sheet(sheet, HEADERS, rows)

if __name__ == "__main__":
    run(get_date_input())
