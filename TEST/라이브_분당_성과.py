"""라이브 분당 성과 → Google Sheets '라이브_분당_성과' 탭
라이브 목록 먼저 조회 후 각 라이브별 분당 데이터 수집
"""
from _공통 import call_api, get_sheet, write_to_sheet, get_date_input, make_sign, get_current_token, BASE_URL, APP_KEY, SHOP_CIPHER
from urllib.parse import urlencode, quote
from datetime import datetime, timedelta
import requests
import time

SHEET_NAME = "라이브_분당_성과"
LIST_PATH = "/analytics/202509/shop_lives/performance"

HEADERS = ["날짜", "라이브ID", "분(timestamp)", "동시시청자수", "누적시청자수", "좋아요수", "상품클릭수"]

def fetch_per_minutes(live_id: str, page_token=None):
    path = f"/analytics/202510/shop_lives/{live_id}/performance_per_minutes"
    for attempt in range(1, 4):
        timestamp = str(int(time.time()))
        params = {
            "app_key": APP_KEY,
            "currency": "USD",
            "shop_cipher": SHOP_CIPHER,
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
    print(f"\n=== 라이브 분당 성과 [{date_str}] ===")
    sheet = get_sheet(SHEET_NAME)

    next_day = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

    # 라이브 목록 조회
    result = call_api(LIST_PATH, {
        "start_date_ge": date_str,
        "end_date_lt": next_day,
        "currency": "USD",
        "account_type": "ALL",
        "page_size": "100",
    })
    if not result:
        print("  라이브 목록 조회 실패")
        return

    data = result.get("data") or {}
    lives = data.get("lives") or data.get("list") or []

    if not lives:
        print("  해당 날짜 라이브 없음")
        return

    all_rows = []
    for live in lives:
        live_id = live.get("live_id") or live.get("id") or ""
        if not live_id:
            continue

        print(f"  라이브 [{live_id}] 분당 데이터 수집 중...")
        page_token = None
        while True:
            detail = fetch_per_minutes(live_id, page_token)
            if not detail:
                break

            detail_data = detail.get("data") or {}
            items = detail_data.get("performances") or detail_data.get("list") or []

            for item in items:
                metrics = item.get("metrics") or item
                all_rows.append([
                    date_str,
                    live_id,
                    item.get("minute") or item.get("timestamp") or "",
                    metrics.get("concurrent_viewers") or "",
                    metrics.get("total_viewers") or "",
                    metrics.get("likes") or "",
                    metrics.get("product_clicks") or "",
                ])

            next_token = detail_data.get("next_page_token")
            if not next_token or next_token == page_token:
                break
            page_token = next_token

    write_to_sheet(sheet, HEADERS, all_rows)

if __name__ == "__main__":
    run(get_date_input())
