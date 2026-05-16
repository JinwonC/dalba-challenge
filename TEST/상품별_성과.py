"""상품별 성과 → Google Sheets '상품별_성과' 탭"""
from _공통 import call_api, get_sheet, write_to_sheet, get_date_input

SHEET_NAME = "상품별_성과"
PATH = "/analytics/202309/products/performance"

HEADERS = ["날짜", "상품ID", "상품명", "페이지뷰", "클릭수", "CTR", "주문수", "GMV", "구매전환율"]

def run(date_str: str):
    print(f"\n=== 상품별 성과 [{date_str}] ===")
    sheet = get_sheet(SHEET_NAME)

    page_token = None
    all_rows = []

    while True:
        params = {
            "start_date": date_str,
            "end_date": date_str,
            "page_size": "100",
        }
        if page_token:
            params["page_token"] = page_token

        result = call_api(PATH, params)
        if not result:
            break

        data = result.get("data") or {}
        items = data.get("products") or data.get("list") or []

        for item in items:
            all_rows.append([
                date_str,
                item.get("product_id") or item.get("id") or "",
                item.get("product_name") or item.get("name") or "",
                item.get("page_views") or item.get("pv") or "",
                item.get("product_clicks") or item.get("clicks") or "",
                item.get("click_through_rate") or item.get("ctr") or "",
                item.get("orders") or item.get("order_count") or "",
                item.get("gmv") or "",
                item.get("conversion_rate") or "",
            ])

        next_token = data.get("next_page_token")
        if not next_token or next_token == page_token:
            break
        page_token = next_token

    write_to_sheet(sheet, HEADERS, all_rows)

if __name__ == "__main__":
    run(get_date_input())
