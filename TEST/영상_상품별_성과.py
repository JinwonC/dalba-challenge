"""영상 상품별 성과 → Google Sheets '영상_상품별_성과' 탭
영상 목록 먼저 조회 후 각 영상별 상품 성과 수집
"""
from _공통 import call_api, get_sheet, write_to_sheet, get_date_input, make_sign, get_current_token, BASE_URL, APP_KEY, SHOP_CIPHER
from urllib.parse import urlencode, quote
from datetime import datetime, timedelta
import requests
import time

SHEET_NAME = "영상_상품별_성과"
VIDEO_LIST_PATH = "/analytics/202409/shop_videos/performance"

HEADERS = ["날짜", "영상ID", "상품ID", "상품명", "GMV", "통화", "주문수", "판매수량", "클릭수"]

def fetch_video_products(video_id: str, date_str: str, next_day: str, page_token=None):
    path = f"/analytics/202509/shop_videos/{video_id}/products/performance"
    for attempt in range(1, 4):
        timestamp = str(int(time.time()))
        params = {
            "app_key": APP_KEY,
            "currency": "USD",
            "shop_cipher": SHOP_CIPHER,
            "start_date_ge": date_str,
            "end_date_lt": next_day,
            "page_size": "100",
            "sort_field": "gmv",
            "sort_order": "DESC",
            "timestamp": timestamp,
        }
        if page_token:
            params["page_token"] = page_token
        params["sign"] = make_sign(path, params)
        url = BASE_URL + path + "?" + urlencode(params, quote_via=quote)
        headers = {"x-tts-access-token": get_current_token(), "content-type": "application/json"}
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            data = resp.json()
            if data.get("code") == 0:
                return data
            print(f"  [경고] code={data.get('code')}, msg={data.get('message')} (시도 {attempt}/3)")
        except Exception as e:
            print(f"  [오류] {e} (시도 {attempt}/3)")
        time.sleep(2 * attempt)
    return None

def run(date_str: str):
    print(f"\n=== 영상 상품별 성과 [{date_str}] ===")
    sheet = get_sheet(SHEET_NAME)

    next_day = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

    # 영상 목록 조회
    page_token = None
    video_ids = []
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
        result = call_api(VIDEO_LIST_PATH, params)
        if not result:
            break
        data = result.get("data") or {}
        videos = data.get("videos") or []
        for v in videos:
            vid = v.get("id") or v.get("video_id") or ""
            if vid:
                video_ids.append(vid)
        next_token = data.get("next_page_token")
        if not next_token or next_token == page_token:
            break
        page_token = next_token

    if not video_ids:
        print("  해당 날짜 영상 없음")
        return

    print(f"  총 {len(video_ids)}개 영상 상품 성과 수집 중...")
    all_rows = []
    for video_id in video_ids:
        page_token = None
        while True:
            detail = fetch_video_products(video_id, date_str, next_day, page_token)
            if not detail:
                break
            detail_data = detail.get("data") or {}
            items = detail_data.get("products") or detail_data.get("list") or []
            for item in items:
                metrics = item.get("metrics") or item
                gmv = metrics.get("gmv") or {}
                all_rows.append([
                    date_str,
                    video_id,
                    item.get("product_id") or item.get("id") or "",
                    item.get("product_name") or item.get("name") or "",
                    gmv.get("amount") if isinstance(gmv, dict) else gmv or "",
                    gmv.get("currency") if isinstance(gmv, dict) else "USD",
                    metrics.get("order_count") or metrics.get("orders") or "",
                    metrics.get("item_sold_count") or metrics.get("units_sold") or "",
                    metrics.get("product_clicks") or metrics.get("clicks") or "",
                ])
            next_token = detail_data.get("next_page_token")
            if not next_token or next_token == page_token:
                break
            page_token = next_token

    write_to_sheet(sheet, HEADERS, all_rows)

if __name__ == "__main__":
    run(get_date_input())
