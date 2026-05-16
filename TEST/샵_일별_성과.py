"""샵 일별 전체 성과 → Google Sheets '샵_일별_성과' 탭"""
from _공통 import call_api, get_sheet, write_to_sheet, get_date_input

SHEET_NAME = "샵_일별_성과"
PATH = "/analytics/202309/shop/performance"

HEADERS = ["날짜", "페이지뷰", "방문자수", "상품클릭수", "CTR", "주문수", "GMV", "구매전환율", "신규구매자", "재구매자"]

def run(date_str: str):
    print(f"\n=== 샵 일별 성과 [{date_str}] ===")
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
        data.get("page_views") or data.get("pv") or "",
        data.get("unique_visitors") or data.get("uv") or "",
        data.get("product_clicks") or "",
        data.get("click_through_rate") or data.get("ctr") or "",
        data.get("orders") or data.get("order_count") or "",
        data.get("gmv") or data.get("gmv_amount") or "",
        data.get("conversion_rate") or "",
        data.get("new_buyers") or "",
        data.get("return_buyers") or "",
    ]
    write_to_sheet(sheet, HEADERS, [row])

if __name__ == "__main__":
    run(get_date_input())
