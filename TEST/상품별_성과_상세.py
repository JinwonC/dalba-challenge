"""상품별 성과 상세 → Google Sheets '상품별_성과_상세' 탭
주문 1건 이상인 상품만 상세 조회 (채널별 GMV·트래픽·취소환불 포함)
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
    # 전체
    "주문수", "판매수량", "GMV(전체)", "통화",
    # 취소·환불
    "취소수", "환불수", "반품수",
    # 라이브
    "GMV(라이브)", "판매수량(라이브)", "평균구매고객(라이브)", "노출수(라이브)", "페이지뷰(라이브)", "CTR(라이브)", "전환율(라이브)",
    # 영상
    "GMV(영상)", "판매수량(영상)", "평균구매고객(영상)", "노출수(영상)", "페이지뷰(영상)", "CTR(영상)", "전환율(영상)",
    # 상품카드
    "GMV(상품카드)", "판매수량(상품카드)", "평균구매고객(상품카드)", "노출수(상품카드)", "페이지뷰(상품카드)", "CTR(상품카드)", "전환율(상품카드)",
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

def parse_channel(breakdowns, channel_type):
    """채널별 sales/traffic 데이터 추출"""
    sales_data, traffic_data = {}, {}
    for bd in breakdowns:
        if bd.get("content_type") == channel_type:
            sales_data = bd.get("sales") or {}
            traffic_data = bd.get("traffic") or {}
            break
    return sales_data, traffic_data

def run(date_str: str):
    print(f"\n=== 상품별 성과 상세 [{date_str}] ===")
    sheet = get_sheet(SHEET_NAME)

    next_day = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

    # 1. 상품 목록 조회 (주문 1건 이상만)
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

        intervals = (detail.get("data") or {}).get("performance", {}).get("intervals") or []
        if not intervals:
            continue
        inv = intervals[0]

        sales = inv.get("sales") or {}
        gmv = sales.get("gmv") or {}
        cr  = inv.get("cancel_and_refunds") or {}

        sales_bds   = sales.get("breakdowns") or []
        traffic_bds = (inv.get("traffic") or {}).get("breakdowns") or []

        # 채널별 breakdowns를 딕셔너리로 변환
        sales_by_channel   = {bd.get("content_type"): bd.get("sales") or {}   for bd in sales_bds}
        traffic_by_channel = {bd.get("content_type"): bd.get("traffic") or {} for bd in traffic_bds}

        def s(channel): return sales_by_channel.get(channel, {})
        def t(channel): return traffic_by_channel.get(channel, {})

        all_rows.append([
            date_str,
            product_id,
            # 전체
            sales.get("orders") or "",
            sales.get("items_sold") or "",
            gmv.get("amount") or "",
            gmv.get("currency") or "USD",
            # 취소·환불
            cr.get("canceled") or "",
            cr.get("refunded") or "",
            cr.get("returned") or "",
            # 라이브
            (s("LIVE").get("gmv") or {}).get("amount") or "",
            s("LIVE").get("items_sold") or "",
            s("LIVE").get("avg_customers") or "",
            t("LIVE").get("impressions") or "",
            t("LIVE").get("page_views") or "",
            t("LIVE").get("ctr") or "",
            t("LIVE").get("avg_conversion_rate") or "",
            # 영상
            (s("VIDEO").get("gmv") or {}).get("amount") or "",
            s("VIDEO").get("items_sold") or "",
            s("VIDEO").get("avg_customers") or "",
            t("VIDEO").get("impressions") or "",
            t("VIDEO").get("page_views") or "",
            t("VIDEO").get("ctr") or "",
            t("VIDEO").get("avg_conversion_rate") or "",
            # 상품카드
            (s("PRODUCT_CARD").get("gmv") or {}).get("amount") or "",
            s("PRODUCT_CARD").get("items_sold") or "",
            s("PRODUCT_CARD").get("avg_customers") or "",
            t("PRODUCT_CARD").get("impressions") or "",
            t("PRODUCT_CARD").get("page_views") or "",
            t("PRODUCT_CARD").get("ctr") or "",
            t("PRODUCT_CARD").get("avg_conversion_rate") or "",
        ])

    write_to_sheet(sheet, HEADERS, all_rows)

if __name__ == "__main__":
    run(get_date_input())
