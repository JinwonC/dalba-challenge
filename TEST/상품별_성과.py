"""상품별 성과 → Google Sheets '상품별_성과' 탭"""
from _공통 import call_api, get_sheet, write_to_sheet, get_date_input
from datetime import datetime, timedelta

SHEET_NAME = "상품별_성과"
PATH = "/analytics/202509/shop_products/performance"

HEADERS = ["날짜", "상품ID", "상품명", "페이지뷰", "클릭수", "CTR", "주문수", "GMV", "통화", "판매수량", "구매전환율"]

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
        items = data.get("products") or data.get("list") or []

        for item in items:
            metrics = item.get("metrics") or item
            gmv = metrics.get("gmv") or {}
            all_rows.append([
                date_str,
                item.get("product_id") or item.get("id") or "",
                item.get("product_name") or item.get("name") or "",
                metrics.get("page_views") or metrics.get("pv") or "",
                metrics.get("product_clicks") or metrics.get("clicks") or "",
                metrics.get("click_through_rate") or metrics.get("ctr") or "",
                metrics.get("order_count") or metrics.get("orders") or "",
                gmv.get("amount") if isinstance(gmv, dict) else gmv or "",
                gmv.get("currency") if isinstance(gmv, dict) else "USD",
                metrics.get("item_sold_count") or metrics.get("units_sold") or "",
                metrics.get("conversion_rate") or "",
            ])

        next_token = data.get("next_page_token")
        if not next_token or next_token == page_token:
            break
        page_token = next_token

    write_to_sheet(sheet, HEADERS, all_rows)

if __name__ == "__main__":
    run(get_date_input())
