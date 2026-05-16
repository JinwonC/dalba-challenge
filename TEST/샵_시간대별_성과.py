"""샵 시간대별 성과 → Google Sheets '샵_시간대별_성과' 탭"""
from _공통 import call_api, get_sheet, write_to_sheet, get_date_input

SHEET_NAME = "샵_시간대별_성과"
PATH = "/analytics/202309/shop/performance/hourly"

HEADERS = ["날짜", "시간(0~23)", "페이지뷰", "방문자수", "주문수", "GMV"]

def run(date_str: str):
    print(f"\n=== 샵 시간대별 성과 [{date_str}] ===")
    sheet = get_sheet(SHEET_NAME)

    result = call_api(PATH, {"date": date_str})

    if not result:
        print("  API 호출 실패")
        return

    items = result.get("data") or []
    if isinstance(items, dict):
        items = items.get("list") or items.get("hourly_data") or []

    rows = []
    for item in items:
        rows.append([
            date_str,
            item.get("hour") or item.get("time") or "",
            item.get("page_views") or item.get("pv") or "",
            item.get("unique_visitors") or item.get("uv") or "",
            item.get("orders") or item.get("order_count") or "",
            item.get("gmv") or "",
        ])
    write_to_sheet(sheet, HEADERS, rows)

if __name__ == "__main__":
    run(get_date_input())
