"""상품별 성과 상세 → Google Sheets '상품별_성과_상세' 탭
주문 1건 이상인 상품만 상세 조회
"""
from _공통 import call_api, get_sheet, write_to_sheet, get_date_input, make_sign, get_current_token, BASE_URL, APP_KEY, SHOP_CIPHER
from urllib.parse import urlencode, quote
from datetime import datetime, timedelta
import requests
import time

SHEET_NAME = "상품별_성과_상세"
LIST_PATH = "/analytics/202509/shop_products/performance"

HEADERS = [
    "날짜", "상품ID",
    "주문수", "판매수량", "GMV", "통화",
    "GMV(라이브)", "GMV(영상)", "GMV(상품카드)",
    "방문자수", "페이지뷰", "상품클릭수", "CTR", "구매전환율"
]

def fetch_detail(product_id: str, date_str: str, next_day: str):
    path = f"/analytics/202509/shop_products/{product_id}/performance"
    for attempt in range(1, 4):
        timestamp = str(int(time.time()))
        params = {
            "app_key": APP_KEY,
            "currency": "USD",
            "end_date_lt": next_day,
            "granularity": "ALL",
            "shop_cipher": SHOP_CIPHER,
            "start_date_ge": date_str,
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
            print(f"  [경고] {product_id}: code={data.get('code')}, msg={data.get('message')} (시도 {attempt}/3)")
        except Exception as e:
            print(f"  [오류] {product_id}: {e} (시도 {attempt}/3)")
        time.sleep(2 * attempt)
    return None

def run(date_str: str):
    print(f"\n=== 상품별 성과 상세 [{date_str}] ===")
    sheet = get_sheet(SHEET_NAME)

    next_day = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

    # 1. 상품 목록 조회 (주문 1건 이상만 필터)
    page_token = None
    product_ids = []
    while True:
        params = {
            "start_date_ge": date_str,
            "end_date_lt": next_day,
            "currency": "USD",
            "page_size": "100",
            "sort_field": "gmv",
            "sort_order": "DESC",
        }
        if page_token:
            params["page_token"] = page_token
        result = call_api(LIST_PATH, params)
        if not result:
            break
        data = result.get("data") or {}
        for item in data.get("products") or []:
            orders = (item.get("overall_performance") or {}).get("orders") or 0
            if int(orders) >= 1:
                product_ids.append(item.get("id"))
        next_token = data.get("next_page_token")
        if not next_token or next_token == page_token:
            break
        page_token = next_token

    if not product_ids:
        print("  주문 1건 이상 상품 없음")
        return

    print(f"  총 {len(product_ids)}개 상품 상세 조회 중...")
    all_rows = []
    for product_id in product_ids:
        detail = fetch_detail(product_id, date_str, next_day)
        if not detail:
            continue

        # 실제 응답 구조에 맞게 파싱 (진단 후 수정 예정)
        d = detail.get("data") or {}
        intervals = (d.get("performance") or {}).get("intervals") or []
        perf = intervals[0] if intervals else d.get("overall_performance") or d

        gmv = perf.get("gmv") or {}
        breakdowns = (perf.get("gmv") or {}).get("breakdowns") or []
        gmv_live = gmv_video = gmv_card = ""
        for bd in breakdowns:
            val = (bd.get("gmv") or {}).get("amount") or bd.get("amount") or ""
            t = bd.get("type") or ""
            if t == "LIVE":       gmv_live  = val
            elif t == "VIDEO":    gmv_video = val
            elif t == "PRODUCT_CARD": gmv_card = val

        traffic = perf.get("traffic") or {}
        sales   = perf.get("sales") or perf

        all_rows.append([
            date_str,
            product_id,
            sales.get("orders") or perf.get("orders") or "",
            sales.get("items_sold") or perf.get("items_sold") or "",
            gmv.get("amount") or perf.get("gmv_amount") or "",
            gmv.get("currency") or "USD",
            gmv_live,
            gmv_video,
            gmv_card,
            traffic.get("visitors") or perf.get("visitors") or "",
            traffic.get("page_views") or perf.get("page_views") or "",
            traffic.get("product_clicks") or perf.get("product_clicks") or "",
            traffic.get("click_through_rate") or perf.get("click_through_rate") or "",
            traffic.get("conversion_rate") or perf.get("conversion_rate") or "",
        ])

    write_to_sheet(sheet, HEADERS, all_rows)

if __name__ == "__main__":
    run(get_date_input())
