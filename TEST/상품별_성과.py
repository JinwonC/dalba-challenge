"""상품별 성과 → Google Sheets '상품별_성과' 탭"""
from _공통 import call_api, get_sheet, write_to_sheet, get_date_input
from datetime import datetime, timedelta

SHEET_NAME = "상품별_성과"
PATH = "/analytics/202509/shop_products/performance"

HEADERS = ["날짜", "상품ID", "주문수", "판매수량", "GMV", "통화"]

def run(date_str: str):
    print(f"\n=== 상품별 성과 [{date_str}] ===")
    sheet = get_sheet(SHEET_NAME)

    next_day = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    page_token = None
    all_rows = []

    while True:
        params = {
            "start_date_ge": date_str,
            "end_date_lt": next_day,
            "currency": "USD",
            "page_size": "100",
            "sort_field": "gmv",
            "sort_order": "DESC",
        }
        if page_token:
            params["page_token"] = page_token

        result = call_api(PATH, params)
        if not result:
            break

        data = result.get("data") or {}
        items = data.get("products") or []

        for item in items:
            perf = item.get("overall_performance") or {}
            gmv = perf.get("gmv") or {}
            all_rows.append([
                date_str,
                item.get("id") or "",
                perf.get("orders") or "",
                perf.get("items_sold") or "",
                gmv.get("amount") or "",
                gmv.get("currency") or "USD",
            ])

        next_token = data.get("next_page_token")
        if not next_token or next_token == page_token:
            break
        page_token = next_token

    write_to_sheet(sheet, HEADERS, all_rows)

if __name__ == "__main__":
    run(get_date_input())
