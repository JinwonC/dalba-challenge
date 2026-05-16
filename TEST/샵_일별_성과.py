"""샵 일별 전체 성과 → Google Sheets '샵_일별_성과' 탭"""
from _공통 import call_api, get_sheet, write_to_sheet, get_date_input
from datetime import datetime, timedelta

SHEET_NAME = "샵_일별_성과"
PATH = "/analytics/202509/shop/performance"

HEADERS = [
    "날짜", "방문자수", "페이지뷰", "구매전환율",
    "주문수", "SKU주문수", "판매수량", "평균구매고객수",
    "GMV(전체)", "GMV(라이브)", "GMV(영상)", "GMV(상품카드)",
    "총매출", "환불금액", "통화"
]

def run(date_str: str):
    print(f"\n=== 샵 일별 성과 [{date_str}] ===")
    sheet = get_sheet(SHEET_NAME)

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

    intervals = result.get("data", {}).get("performance", {}).get("intervals", [])
    if not intervals:
        print("  데이터 없음")
        return

    rows = []
    for interval in intervals:
        traffic = interval.get("traffic") or {}
        sales = interval.get("sales") or {}
        gmv_overall = (sales.get("gmv") or {}).get("overall") or {}
        gross = (sales.get("gross_revenue") or {}).get("overall") or {}
        refunds = sales.get("refunds") or {}
        currency = gmv_overall.get("currency") or "USD"

        # GMV 브레이크다운
        breakdowns = (sales.get("gmv") or {}).get("breakdowns") or []
        gmv_live = gmv_video = gmv_card = ""
        for bd in breakdowns:
            val = (bd.get("gmv") or {}).get("amount") or ""
            if bd.get("type") == "LIVE":
                gmv_live = val
            elif bd.get("type") == "VIDEO":
                gmv_video = val
            elif bd.get("type") == "PRODUCT_CARD":
                gmv_card = val

        rows.append([
            interval.get("start_date") or date_str,
            traffic.get("avg_visitors") or "",
            traffic.get("avg_page_views") or "",
            traffic.get("avg_conversation_rate") or "",
            sales.get("orders_count") or "",
            sales.get("sku_orders_count") or "",
            sales.get("items_sold") or "",
            sales.get("avg_customers_count") or "",
            gmv_overall.get("amount") or "",
            gmv_live,
            gmv_video,
            gmv_card,
            gross.get("amount") or "",
            refunds.get("amount") or "",
            currency,
        ])

    write_to_sheet(sheet, HEADERS, rows)

if __name__ == "__main__":
    run(get_date_input())
