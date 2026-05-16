"""라이브 상품별 성과 → Google Sheets '라이브_상품별_성과' 탭
라이브 목록 먼저 조회 후 각 라이브별 상품 성과 수집
"""
from _공통 import call_api, get_sheet, write_to_sheet, get_date_input, make_sign, get_current_token, BASE_URL, APP_KEY, SHOP_CIPHER
from urllib.parse import urlencode, quote
from datetime import datetime, timedelta
import requests
import time

SHEET_NAME = "라이브_상품별_성과"
LIST_PATH = "/analytics/202509/shop_lives/performance"

HEADERS = ["날짜", "라이브ID", "상품ID", "상품명", "직접GMV", "통화", "주문수", "판매수량", "클릭수"]

NO_PERMISSION = 28001022

def fetch_live_products(live_id: str, page_token=None):
    path = f"/analytics/202512/shop/{live_id}/products_performance"
    for attempt in range(1, 4):
        timestamp = str(int(time.time()))
        params = {
            "app_key": APP_KEY,
            "currency": "USD",
            "shop_cipher": SHOP_CIPHER,
            "sort_field": "direct_gmv",
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
            if data.get("code") == NO_PERMISSION:
                return {"no_permission": True}
            print(f"  [경고] code={data.get('code')}, msg={data.get('message')} (시도 {attempt}/3)")
        except Exception as e:
            print(f"  [오류] {e} (시도 {attempt}/3)")
        time.sleep(2 * attempt)
    return None

def run(date_str: str):
    print(f"\n=== 라이브 상품별 성과 [{date_str}] ===")
    sheet = get_sheet(SHEET_NAME)

    next_day = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

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
    lives = data.get("live_stream_sessions") or []

    if not lives:
        print("  해당 날짜 라이브 없음")
        return

    all_rows = []
    for live in lives:
        live_id = live.get("id") or ""
        if not live_id:
            continue

        print(f"  라이브 [{live_id}] 상품 성과 수집 중...")
        page_token = None
        while True:
            detail = fetch_live_products(live_id, page_token)
            if not detail:
                break
            if detail.get("no_permission"):
                print("  ❌ 권한 없음 (TikTok 앱에서 라이브 상품별 성과 API 권한 필요) - 종료")
                write_to_sheet(sheet, HEADERS, all_rows)
                return

            detail_data = detail.get("data") or {}
            items = detail_data.get("products") or detail_data.get("list") or []

            for item in items:
                metrics = item.get("metrics") or item
                gmv = metrics.get("direct_gmv") or metrics.get("gmv") or {}
                all_rows.append([
                    date_str,
                    live_id,
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
