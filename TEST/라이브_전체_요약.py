"""라이브 전체 요약 → Google Sheets '라이브_전체_요약' 탭"""
from _공통 import call_api, get_sheet, write_to_sheet, get_date_input
from datetime import datetime, timedelta

SHEET_NAME = "라이브_전체_요약"
PATH = "/analytics/202509/shop_lives/overview_performance"

HEADERS = ["날짜(시작)", "날짜(종료)", "구매고객수", "GMV", "통화", "SKU주문수", "판매수량", "CTR", "주문전환율"]

def run(date_str: str):
    print(f"\n=== 라이브 전체 요약 [{date_str}] ===")
    sheet = get_sheet(SHEET_NAME)

    next_day = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

    result = call_api(PATH, {
        "start_date_ge": date_str,
        "end_date_lt": next_day,
        "granularity": "1D",
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
            item.get("customers") or "",
            gmv.get("amount") or "",
            gmv.get("currency") or "USD",
            item.get("sku_orders") or "",
            item.get("items_sold") or "",
            item.get("click_through_rate") or "",
            item.get("click_to_order_rate") or "",
        ])

    write_to_sheet(sheet, HEADERS, rows)

if __name__ == "__main__":
    run(get_date_input())
