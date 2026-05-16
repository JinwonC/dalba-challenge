"""라이브 성과 목록 → Google Sheets '라이브_성과' 탭"""
from _공통 import call_api, get_sheet, write_to_sheet, get_date_input
from datetime import datetime, timedelta

SHEET_NAME = "라이브_성과"
PATH = "/analytics/202509/shop_lives/performance"

HEADERS = [
    "날짜", "라이브ID", "계정", "시작시간(unix)", "종료시간(unix)",
    "GMV", "24h GMV", "통화", "SKU주문수", "생성SKU주문수", "판매수량",
    "구매고객수", "판매상품종류수", "추가상품수", "평균단가", "주문전환율",
    "시청자수", "조회수", "평균시청시간(초)", "좋아요", "댓글", "공유",
    "신규팔로워", "상품클릭수", "상품노출수", "CTR"
]

def run(date_str: str):
    print(f"\n=== 라이브 성과 [{date_str}] ===")
    sheet = get_sheet(SHEET_NAME)

    next_day = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    page_token = None
    all_rows = []

    while True:
        params = {
            "start_date_ge": date_str,
            "end_date_lt": next_day,
            "currency": "USD",
            "account_type": "ALL",
            "page_size": "100",
        }
        if page_token:
            params["page_token"] = page_token

        result = call_api(PATH, params)
        if not result:
            break

        data = result.get("data") or {}
        items = data.get("live_stream_sessions") or []

        for item in items:
            sales = item.get("sales_performance") or {}
            inter = item.get("interaction_performance") or {}
            gmv = sales.get("gmv") or {}
            gmv_24h = sales.get("24h_live_gmv") or {}
            avg_price = sales.get("avg_price") or {}
            all_rows.append([
                date_str,
                item.get("id") or "",
                item.get("username") or "",
                item.get("start_time") or "",
                item.get("end_time") or "",
                gmv.get("amount") or "",
                gmv_24h.get("amount") or "",
                gmv.get("currency") or "USD",
                sales.get("sku_orders") or "",
                sales.get("created_sku_orders") or "",
                sales.get("items_sold") or "",
                sales.get("customers") or "",
                sales.get("different_products_sold") or "",
                sales.get("products_added") or "",
                avg_price.get("amount") or "",
                sales.get("click_to_order_rate") or "",
                inter.get("viewers") or "",
                inter.get("views") or "",
                inter.get("avg_viewing_duration") or "",
                inter.get("likes") or "",
                inter.get("comments") or "",
                inter.get("shares") or "",
                inter.get("new_followers") or "",
                inter.get("product_clicks") or "",
                inter.get("product_impressions") or "",
                inter.get("click_through_rate") or "",
            ])

        next_token = data.get("next_page_token")
        if not next_token or next_token == page_token:
            break
        page_token = next_token

    write_to_sheet(sheet, HEADERS, all_rows)

if __name__ == "__main__":
    run(get_date_input())
