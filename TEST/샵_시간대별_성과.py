"""샵 시간대별 성과 → Google Sheets '샵_시간대별_성과' 탭
날짜가 URL 경로에 들어가는 구조입니다.
"""
from _공통 import get_sheet, write_to_sheet, get_date_input, make_sign, get_current_token, BASE_URL, APP_KEY, SHOP_CIPHER
from urllib.parse import urlencode, quote
import requests
import time

SHEET_NAME = "샵_시간대별_성과"

HEADERS = ["날짜", "시간(0~23)", "방문자수", "구매고객수", "판매수량", "GMV", "통화"]

def fetch(date_str: str):
    path = f"/analytics/202510/shop/performance/{date_str}/performance_per_hour"
    for attempt in range(1, 4):
        timestamp = str(int(time.time()))
        params = {
            "app_key": APP_KEY,
            "currency": "USD",
            "shop_cipher": SHOP_CIPHER,
            "timestamp": timestamp,
        }
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
    print(f"\n=== 샵 시간대별 성과 [{date_str}] ===")
    sheet = get_sheet(SHEET_NAME)

    result = fetch(date_str)
    if not result:
        print("  API 호출 실패")
        return

    data = result.get("data") or {}
    performance = data.get("performance") or {}
    items = performance.get("intervals") or []

    rows = []
    for item in items:
        gmv = item.get("gmv") or {}
        rows.append([
            date_str,
            item.get("index", ""),
            item.get("visitors") or "",
            item.get("customers") or "",
            item.get("items_sold") or "",
            gmv.get("amount") or "",
            gmv.get("currency") or "USD",
        ])

    write_to_sheet(sheet, HEADERS, rows)

if __name__ == "__main__":
    run(get_date_input())
