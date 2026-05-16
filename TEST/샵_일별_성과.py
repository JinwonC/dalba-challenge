"""샵 일별 전체 성과 → Google Sheets '샵_일별_성과' 탭"""
from _공통 import call_api, get_sheet, write_to_sheet, get_date_input
from datetime import datetime, timedelta

SHEET_NAME = "샵_일별_성과"
PATH = "/analytics/202509/shop/performance"

HEADERS = ["날짜", "페이지뷰", "방문자수", "상품클릭수", "CTR", "주문수", "GMV", "통화", "구매전환율", "신규구매자", "재구매자"]

def run(date_str: str):
    print(f"\n=== 샵 일별 성과 [{date_str}] ===")
    sheet = get_sheet(SHEET_NAME)

    # end_date_lt는 다음날
    next_day = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

    result = call_api(PATH, {
        "start_date_ge": date_str,
        "end_date_lt": next_day,
        "granularity": "ALL",
        "currency": "USD",
    })

    if not result:
        print("  API 호출 실패")
        return

    data = result.get("data") or {}
    metrics = data.get("metrics") or data

    row = [
        date_str,
        metrics.get("page_views") or metrics.get("pv") or "",
        metrics.get("unique_visitors") or metrics.get("uv") or "",
        metrics.get("product_clicks") or "",
        metrics.get("click_through_rate") or metrics.get("ctr") or "",
        metrics.get("order_count") or metrics.get("orders") or "",
        (metrics.get("gmv") or {}).get("amount") if isinstance(metrics.get("gmv"), dict) else metrics.get("gmv") or "",
        (metrics.get("gmv") or {}).get("currency") if isinstance(metrics.get("gmv"), dict) else "USD",
        metrics.get("conversion_rate") or "",
        metrics.get("new_buyers") or metrics.get("new_customer_count") or "",
        metrics.get("return_buyers") or metrics.get("returning_customer_count") or "",
    ]
    write_to_sheet(sheet, HEADERS, [row])

if __name__ == "__main__":
    run(get_date_input())
