"""SKU별 성과 → Google Sheets '(중요) SKU Order' 탭
주문 데이터에서 product_id → 상품명 자동 매핑
"""
from _공통 import call_api, write_to_sheet, SERVICE_ACCOUNT_FILE, APP_KEY, APP_SECRET, SHOP_CIPHER
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from google.oauth2.service_account import Credentials
import gspread, re, sys, json, time, hmac, hashlib, requests
from urllib.parse import urlencode, quote

SPREADSHEET_ID = "15dP91bH_skc7ZzcJ3ehH9H4IKCzSxcfuOcREr3OaL0o"
SHEET_NAME = "(중요) SKU Order"
SKU_PATH   = "/analytics/202509/shop_skus/performance"
ORDER_PATH = "/order/202309/orders/search"
BASE_URL   = "https://open-api.tiktokglobalshop.com"
TOKEN_FILE_PATH = __import__('os').path.join(__import__('os').path.dirname(__import__('os').path.abspath(__file__)), "..", "tokens.json")
LA_TZ = ZoneInfo("America/Los_Angeles")

HEADERS = ["날짜", "상품ID", "상품명", "SKU ID", "SKU주문수", "판매수량", "GMV", "통화"]


def get_token():
    import json as _json, os
    if os.path.exists(TOKEN_FILE_PATH):
        with open(TOKEN_FILE_PATH) as f:
            return _json.load(f).get("access_token", "")
    return ""


def get_target_sheet():
    creds = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"]
    )
    spreadsheet = gspread.authorize(creds).open_by_key(SPREADSHEET_ID)
    try:
        return spreadsheet.worksheet(SHEET_NAME)
    except gspread.WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title=SHEET_NAME, rows="5000", cols="10")
        print(f"  시트 '{SHEET_NAME}' 새로 생성됨")
        return sheet


def parse_date_range(raw: str):
    nums = re.findall(r"\d{4}[-./]\d{1,2}[-./]\d{1,2}", raw)
    if len(nums) == 1:
        return nums[0], nums[0]
    if len(nums) >= 2:
        return re.sub(r"[./]", "-", nums[0]), re.sub(r"[./]", "-", nums[1])
    raise ValueError("날짜 형식 오류. 예: 2026-05-01 또는 2026-05-01 ~ 2026-05-15")


# ─────────────────────────────────────────
# 주문 API에서 product_id → 상품명 매핑 구축
# ─────────────────────────────────────────
def make_order_sign(path, params, body):
    s = APP_SECRET + path
    for k in sorted(params.keys()):
        s += k + str(params[k])
    if body:
        s += body
    s += APP_SECRET
    return hmac.new(APP_SECRET.encode(), s.encode(), hashlib.sha256).hexdigest()


def fetch_product_name_map(start_date: str, end_date: str) -> dict:
    """상품명 매핑: 전체 기간 대신 최근 30일만 조회 (상품명은 변하지 않음)"""
    from datetime import date
    # 최근 30일로 제한 (너무 긴 기간이면 속도 저하)
    lookup_end = datetime.now(LA_TZ)
    lookup_start = lookup_end - timedelta(days=30)

    name_map = {}
    page_token = None

    while True:
        body_obj = {
            "create_time_ge": int(lookup_start.timestamp()),
            "create_time_lt": int(lookup_end.timestamp()),
        }
        body = json.dumps(body_obj, separators=(",", ":"))
        params = {
            "app_key": APP_KEY,
            "page_size": "50",
            "shop_cipher": SHOP_CIPHER,
            "sort_field": "create_time",
            "sort_order": "ASC",
            "timestamp": str(int(time.time())),
        }
        if page_token:
            params["page_token"] = page_token
        params["sign"] = make_order_sign(ORDER_PATH, params, body)

        url = BASE_URL + ORDER_PATH + "?" + urlencode(params, quote_via=quote)
        hdrs = {"x-tts-access-token": get_token(), "content-type": "application/json"}
        try:
            r = requests.post(url, headers=hdrs, data=body, timeout=60)
            d = r.json()
        except Exception as e:
            print(f"  [주문 API 오류] {e}")
            break

        if d.get("code") != 0:
            print(f"  [주문 API 경고] code={d.get('code')}, msg={d.get('message')}")
            break

        orders = (d.get("data") or {}).get("orders") or []
        for order in orders:
            for item in (order.get("line_items") or []):
                pid = str(item.get("product_id", ""))
                pname = item.get("product_name", "")
                if pid and pname:
                    name_map[pid] = pname

        next_token = (d.get("data") or {}).get("next_page_token")
        if not next_token or next_token == page_token:
            break
        page_token = next_token
        time.sleep(0.3)

    print(f"  상품명 매핑 {len(name_map)}개 구축")
    return name_map


# ─────────────────────────────────────────
# SKU 성과 조회
# ─────────────────────────────────────────
def run(date_str: str, name_map: dict):
    next_day = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    page_token = None
    all_rows = []

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

        result = call_api(SKU_PATH, params)
        if not result:
            break

        data = result.get("data") or {}
        for item in (data.get("skus") or []):
            gmv = item.get("gmv") or {}
            pid = str(item.get("product_id") or "")
            all_rows.append([
                date_str,
                "'" + pid,
                name_map.get(pid, ""),
                "'" + str(item.get("id") or ""),
                item.get("sku_orders") or 0,
                item.get("units_sold") or 0,
                gmv.get("amount") or 0,
                gmv.get("currency") or "USD",
            ])

        next_token = data.get("next_page_token")
        if not next_token or next_token == page_token:
            break
        page_token = next_token

    return all_rows


# ─────────────────────────────────────────
# 메인
# ─────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) > 1:
        raw = sys.argv[1]
    else:
        raw = input("기간 입력 (예: 2026-05-01 또는 2026-05-01 ~ 2026-05-15): ").strip()

    start_str, end_str = parse_date_range(raw)
    sheet = get_target_sheet()

    print(f"  주문 데이터에서 상품명 매핑 중...")
    name_map = fetch_product_name_map(start_str, end_str)

    current = datetime.strptime(start_str, "%Y-%m-%d")
    end     = datetime.strptime(end_str, "%Y-%m-%d")

    total = 0
    while current <= end:
        date_str = current.strftime("%Y-%m-%d")
        print(f"\n=== SKU별 성과 [{date_str}] ===")
        rows = run(date_str, name_map)
        if rows:
            write_to_sheet(sheet, HEADERS, rows)
            total += len(rows)
        else:
            print("  데이터 없음")
        current += timedelta(days=1)

    print(f"\n총 {total}행 저장 완료")
