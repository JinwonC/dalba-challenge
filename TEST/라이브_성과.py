"""라이브 성과 목록 → Google Sheets '라이브_성과' 탭"""
from _공통 import call_api, get_sheet, write_to_sheet, get_date_input

SHEET_NAME = "라이브_성과"
PATH = "/analytics/202309/lives/performance"

HEADERS = ["날짜", "라이브ID", "제목", "시작시간", "종료시간", "시청자수", "최대동시시청", "주문수", "GMV", "상품클릭수"]

def run(date_str: str):
    print(f"\n=== 라이브 성과 [{date_str}] ===")
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
        items = data.get("lives") or data.get("list") or []

        for item in items:
            all_rows.append([
                date_str,
                item.get("live_id") or item.get("id") or "",
                item.get("title") or "",
                item.get("start_time") or "",
                item.get("end_time") or "",
                item.get("viewers") or item.get("total_viewers") or "",
                item.get("peak_viewers") or item.get("peak_concurrent_viewers") or "",
                item.get("orders") or item.get("order_count") or "",
                item.get("gmv") or "",
                item.get("product_clicks") or "",
            ])

        next_token = data.get("next_page_token")
        if not next_token or next_token == page_token:
            break
        page_token = next_token

    write_to_sheet(sheet, HEADERS, all_rows)

if __name__ == "__main__":
    run(get_date_input())
