"""주문 API → '리스팅' 탭에 상품ID/상품명/SKU ID/SKU명 적재 (중복 제거)"""
from _공통 import get_current_token, SERVICE_ACCOUNT_FILE
from datetime import datetime, timedelta, timezone
from google.oauth2.service_account import Credentials
import gspread, json, hmac, hashlib, time, re, sys, requests
from urllib.parse import urlencode, quote

SPREADSHEET_ID = "15dP91bH_skc7ZzcJ3ehH9H4IKCzSxcfuOcREr3OaL0o"
SHEET_NAME     = "리스팅"
BASE_URL       = "https://open-api.tiktokglobalshop.com"
ORDER_PATH     = "/order/202309/orders/search"
APP_KEY        = "6jd7l2nu36rd4"
APP_SECRET     = "9ab6f9c3467d53c72ca6e346c18b8071338f0ce4"
SHOP_CIPHER    = "TTP_uE19hAAAAADx5Flb4Y_fjmWFiQfOEyTT"

HEADERS = ["상품ID", "상품명", "SKU ID", "SKU명"]


def _sign(params, body):
    s = APP_SECRET + ORDER_PATH
    for k in sorted(params.keys()):
        s += k + str(params[k])
    if body:
        s += body
    s += APP_SECRET
    return hmac.new(APP_SECRET.encode(), s.encode(), hashlib.sha256).hexdigest()


def fetch_orders(from_ts, to_ts, page_token=None):
    body = json.dumps({"create_time_ge": from_ts, "create_time_lt": to_ts}, separators=(",", ":"))
    ts = str(int(time.time()))
    params = {"app_key": APP_KEY, "page_size": "50", "shop_cipher": SHOP_CIPHER,
              "sort_field": "create_time", "sort_order": "ASC", "timestamp": ts}
    if page_token:
        params["page_token"] = page_token
    params["sign"] = _sign(params, body)
    url = BASE_URL + ORDER_PATH + "?" + urlencode(params, quote_via=quote)
    hdrs = {"x-tts-access-token": get_current_token(), "content-type": "application/json"}
    try:
        r = requests.post(url, headers=hdrs, data=body, timeout=60)
        d = r.json()
        if d.get("code") == 0:
            return d
        print(f"  [경고] code={d.get('code')}, msg={d.get('message')}")
    except Exception as e:
        print(f"  [오류] {e}")
    return None


def parse_date_range(raw):
    nums = re.findall(r"\d{4}[-./]\d{1,2}[-./]\d{1,2}", raw)
    if len(nums) == 1:
        return nums[0], nums[0]
    if len(nums) >= 2:
        return re.sub(r"[./]", "-", nums[0]), re.sub(r"[./]", "-", nums[1])
    raise ValueError("날짜 형식 오류. 예: 2026-05-01 또는 2026-05-01 ~ 2026-05-15")


def main():
    if len(sys.argv) > 1:
        raw = sys.argv[1]
    else:
        raw = input("기간 입력 (예: 2026-05-01 또는 2026-05-01 ~ 2026-05-15): ").strip()

    start_str, end_str = parse_date_range(raw)
    from_ts = int(datetime.strptime(start_str, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
    to_ts   = int((datetime.strptime(end_str, "%Y-%m-%d") + timedelta(days=1)).replace(tzinfo=timezone.utc).timestamp())

    print(f"\n=== 리스팅 수집 [{start_str} ~ {end_str}] ===")

    # 주문 API에서 상품/SKU 정보 수집 (중복 제거)
    seen_skus: set[str] = set()
    rows: list[list] = []
    page_token = None
    page = 1

    while True:
        print(f"  페이지 {page} 조회 중...")
        result = fetch_orders(from_ts, to_ts, page_token)
        if not result:
            break

        for order in (result.get("data") or {}).get("orders") or []:
            for item in (order.get("line_items") or []):
                pid   = str(item.get("product_id") or "").strip()
                pname = str(item.get("product_name") or "").strip()
                sid   = str(item.get("sku_id") or "").strip()
                sname = str(item.get("sku_name") or "").strip()
                key = f"{pid}_{sid}"
                if key in seen_skus or not pid:
                    continue
                seen_skus.add(key)
                rows.append(["'" + pid, pname, "'" + sid, sname])

        next_token = (result.get("data") or {}).get("next_page_token") or ""
        if not next_token or next_token == page_token:
            break
        page_token = next_token
        page += 1
        time.sleep(0.2)

    print(f"  총 {len(rows)}개 SKU 수집")
    if not rows:
        print("  데이터 없음")
        return

    # 기존 리스팅 탭의 SKU ID 읽어서 중복 제거
    creds = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"]
    )
    spreadsheet = gspread.authorize(creds).open_by_key(SPREADSHEET_ID)
    try:
        sheet = spreadsheet.worksheet(SHEET_NAME)
        existing = sheet.get_all_values()
        existing_keys = {
            f"{r[0].lstrip(chr(39))}_{r[2].lstrip(chr(39))}"
            for r in existing[1:] if len(r) >= 3
        }
    except gspread.WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title=SHEET_NAME, rows="5000", cols="5")
        sheet.append_row(HEADERS)
        sheet.freeze(rows=1)
        print(f"  시트 '{SHEET_NAME}' 새로 생성됨")
        existing_keys = set()

    new_rows = [r for r in rows if f"{r[0].lstrip(chr(39))}_{r[2].lstrip(chr(39))}" not in existing_keys]
    print(f"  신규 {len(new_rows)}개 추가 (기존 {len(existing_keys)}개 스킵)")

    if new_rows:
        for attempt in range(1, 6):
            try:
                sheet.append_rows(new_rows, value_input_option="USER_ENTERED")
                print(f"  ✅ {len(new_rows)}행 저장 완료 → '{SHEET_NAME}'")
                break
            except Exception as e:
                if attempt == 5:
                    raise
                wait = min(3 * attempt, 30)
                print(f"  시트 쓰기 실패 (시도 {attempt}/5), {wait}초 후 재시도...")
                time.sleep(wait)


if __name__ == "__main__":
    main()
