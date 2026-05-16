"""라이브 성과 목록 → Google Sheets '라이브_성과' 탭"""
from _공통 import call_api, get_sheet, write_to_sheet, get_date_input
from datetime import datetime, timedelta

SHEET_NAME = "라이브_성과"
PATH = "/analytics/202509/shop_lives/performance"

HEADERS = ["날짜", "라이브ID", "제목", "시작시간", "종료시간", "시청자수", "최대동시시청", "주문수", "GMV", "통화", "상품클릭수", "계정타입"]

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
            "sort_field": "gmv",
            "sort_order": "DESC",
        }
        if page_token:
            params["page_token"] = page_token

        result = call_api(PATH, params)
        if not result:
            break

        data = result.get("data") or {}
        items = data.get("lives") or data.get("list") or []

        for item in items:
            metrics = item.get("metrics") or item
            gmv = metrics.get("gmv") or {}
            all_rows.append([
                date_str,
                item.get("live_id") or item.get("id") or "",
                item.get("title") or "",
                item.get("start_time") or "",
                item.get("end_time") or "",
                metrics.get("total_viewers") or metrics.get("viewers") or "",
                metrics.get("peak_concurrent_viewers") or metrics.get("peak_viewers") or "",
                metrics.get("order_count") or metrics.get("orders") or "",
                gmv.get("amount") if isinstance(gmv, dict) else gmv or "",
                gmv.get("currency") if isinstance(gmv, dict) else "USD",
                metrics.get("product_clicks") or metrics.get("clicks") or "",
                item.get("account_type") or "",
            ])

        next_token = data.get("next_page_token")
        if not next_token or next_token == page_token:
            break
        page_token = next_token

    write_to_sheet(sheet, HEADERS, all_rows)

if __name__ == "__main__":
    run(get_date_input())
