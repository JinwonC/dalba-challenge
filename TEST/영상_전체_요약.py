"""영상 전체 요약 → Google Sheets '영상_전체_요약' 탭"""
from _공통 import call_api, get_sheet, write_to_sheet, get_date_input

SHEET_NAME = "영상_전체_요약"
PATH = "/analytics/202409/shop_videos/overview"

HEADERS = ["날짜", "총영상수", "총조회수", "총GMV", "총주문수", "평균CTR", "평균GPM"]

def run(date_str: str):
    print(f"\n=== 영상 전체 요약 [{date_str}] ===")
    sheet = get_sheet(SHEET_NAME)

    result = call_api(PATH, {
        "start_date_ge": date_str,
        "end_date_lt": date_str,
    })

    if not result:
        print("  API 호출 실패")
        return

    data = result.get("data") or {}
    row = [
        date_str,
        data.get("total_videos") or data.get("video_count") or "",
        data.get("total_views") or data.get("views") or "",
        data.get("total_gmv") or data.get("gmv") or "",
        data.get("total_orders") or data.get("orders") or "",
        data.get("avg_ctr") or data.get("click_through_rate") or "",
        data.get("avg_gpm") or data.get("gpm") or "",
    ]
    write_to_sheet(sheet, HEADERS, [row])

if __name__ == "__main__":
    run(get_date_input())
