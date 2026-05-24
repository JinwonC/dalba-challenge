"""SKU별 성과 → Google Sheets '(중요) SKU Order' 탭"""
from _공통 import call_api, write_to_sheet, SERVICE_ACCOUNT_FILE, get_current_token
from datetime import datetime, timedelta, timezone
from google.oauth2.service_account import Credentials
import gspread, re, sys, json, hmac, hashlib, time, requests
from urllib.parse import urlencode, quote

SPREADSHEET_ID = "15dP91bH_skc7ZzcJ3ehH9H4IKCzSxcfuOcREr3OaL0o"
SHEET_NAME     = "(중요, 자동) SKU Order"
PATH           = "/analytics/202509/shop_skus/performance"

ORDER_PATH  = "/order/202309/orders/search"
BASE_URL    = "https://open-api.tiktokglobalshop.com"
APP_KEY     = "6jd7l2nu36rd4"
APP_SECRET  = "9ab6f9c3467d53c72ca6e346c18b8071338f0ce4"
SHOP_CIPHER = "TTP_uE19hAAAAADx5Flb4Y_fjmWFiQfOEyTT"

HEADERS = ["날짜", "상품ID", "상품명", "SKU ID", "SKU명", "SKU주문수", "판매수량", "GMV", "통화"]


def _order_sign(params, body):
    keys = sorted(params.keys())
    s = APP_SECRET + ORDER_PATH
    for k in keys:
        s += k + str(params[k])
    if body:
        s += body
    s += APP_SECRET
    return hmac.new(APP_SECRET.encode(), s.encode(), hashlib.sha256).hexdigest()


def fetch_order_page(from_ts: int, to_ts: int, page_token=None):
    body_obj = {"create_time_ge": from_ts, "create_time_lt": to_ts}
    body = json.dumps(body_obj, separators=(",", ":"))
    ts = str(int(time.time()))
    params = {"app_key": APP_KEY, "page_size": "50", "shop_cipher": SHOP_CIPHER,
              "sort_field": "create_time", "sort_order": "ASC", "timestamp": ts}
    if page_token:
        params["page_token"] = page_token
    params["sign"] = _order_sign(params, body)
    url = BASE_URL + ORDER_PATH + "?" + urlencode(params, quote_via=quote)
    hdrs = {"x-tts-access-token": get_current_token(), "content-type": "application/json"}
    try:
        r = requests.post(url, headers=hdrs, data=body, timeout=60)
        d = r.json()
        if d.get("code") == 0:
            return d
        print(f"  [주문API 경고] code={d.get('code')}, msg={d.get('message')}")
    except Exception as e:
        print(f"  [주문API 오류] {e}")
    return None


def load_name_maps(start_str: str, end_str: str):
    """조회 기간의 주문 API에서 product_id→상품명, sku_id→SKU명 매핑"""
    print(f"  상품명 매핑 로드 중 ({start_str} ~ {end_str})...")
    from_ts = int(datetime.strptime(start_str, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
    to_ts   = int((datetime.strptime(end_str, "%Y-%m-%d") + timedelta(days=1)).replace(tzinfo=timezone.utc).timestamp())

    product_map: dict[str, str] = {}
    sku_map: dict[str, str] = {}
    page_token = None

    while True:
        result = fetch_order_page(from_ts, to_ts, page_token)
        if not result:
            break
        orders = (result.get("data") or {}).get("orders") or []
        for order in orders:
            for item in (order.get("line_items") or []):
                pid   = str(item.get("product_id") or "").strip()
                pname = str(item.get("product_name") or "").strip()
                sid   = str(item.get("sku_id") or "").strip()
                sname = str(item.get("sku_name") or "").strip()
                if pid and pname and pid not in product_map:
                    product_map[pid] = pname
                if sid and sname and sid not in sku_map:
                    sku_map[sid] = sname

        next_token = (result.get("data") or {}).get("next_page_token") or ""
        if not next_token or next_token == page_token:
            break
        page_token = next_token
        time.sleep(0.2)

    print(f"  상품 {len(product_map)}개, SKU {len(sku_map)}개 매핑 완료")
    return product_map, sku_map


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


def run(date_str: str, product_map: dict, sku_map: dict):
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

        result = call_api(PATH, params)
        if not result:
            break

        data = result.get("data") or {}
        for item in (data.get("skus") or []):
            gmv = item.get("gmv") or {}
            pid = str(item.get("product_id") or "")
            sid = str(item.get("id") or "")
            all_rows.append([
                date_str,
                "'" + pid,
                product_map.get(pid, ""),
                "'" + sid,
                sku_map.get(sid, ""),
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


if __name__ == "__main__":
    if len(sys.argv) > 1:
        raw = sys.argv[1]
    else:
        raw = input("기간 입력 (예: 2026-05-01 또는 2026-05-01 ~ 2026-05-15): ").strip()

    start_str, end_str = parse_date_range(raw)
    product_map, sku_map = load_name_maps(start_str, end_str)
    sheet = get_target_sheet()

    current = datetime.strptime(start_str, "%Y-%m-%d")
    end     = datetime.strptime(end_str, "%Y-%m-%d")

    total = 0
    while current <= end:
        date_str = current.strftime("%Y-%m-%d")
        print(f"\n=== SKU별 성과 [{date_str}] ===")
        rows = run(date_str, product_map, sku_map)
        if rows:
            write_to_sheet(sheet, HEADERS, rows)
            total += len(rows)
        else:
            print("  데이터 없음")
        current += timedelta(days=1)

    print(f"\n총 {total}행 저장 완료")
