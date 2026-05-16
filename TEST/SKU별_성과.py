"""SKU별 성과 → Google Sheets 'SKU별_성과' 탭"""
from _공통 import call_api, get_sheet, write_to_sheet, get_date_input
from datetime import datetime, timedelta

SHEET_NAME = "SKU별_성과"
PATH = "/analytics/202509/shop_skus/performance"

HEADERS = ["날짜", "상품ID", "SKU ID", "SKU주문수", "판매수량", "GMV", "통화"]

def run(date_str: str):
    print(f"\n=== SKU별 성과 [{date_str}] ===")
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
        items = data.get("skus") or []

        for item in items:
            gmv = item.get("gmv") or {}
            all_rows.append([
                date_str,
                item.get("product_id") or "",
                item.get("id") or "",
                item.get("sku_orders") or "",
                item.get("units_sold") or "",
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
