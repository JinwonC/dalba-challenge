"""TikTok Shop Get Order Detail
→ 스프레드시트 1fVWfi... 'Get Order Detail' 탭

/order/202309/orders?ids=... 는 한 번에 여러 주문을 조회할 수 있어
주문ID를 50개씩 묶어 호출한다. 라인아이템 단위 행으로 저장.
기본 기간: 2026-07-01 ~ (양이 많아 7월부터)
"""
import hashlib
import hmac
import json
import re
import sys
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlencode, quote

import requests
from google.oauth2.service_account import Credentials
import gspread
from token_manager import get_valid_token, handle_token_expired

APP_KEY = "6jd7l2nu36rd4"
APP_SECRET = "9ab6f9c3467d53c72ca6e346c18b8071338f0ce4"
ACCESS_TOKEN = "TTP_8qmwDAAAAAAKxe5s-tyxQjFx-BLmHCzEUHx_N8KtbJs8REguA-PlojAyV0wGbdEfcH65GTeVkz7R1pOu5g44xImqf4SrMwS1YxCDFaFiR71wCyyvCuiX9V4xVHdkwwVZjC2fEb9DckyVqVjeUiW-H2PBtsmHPpwLM6krtq-pI3-bR3oq5XS_LA"
REFRESH_TOKEN = "TTP_77fQXQAAAACRYHgjQ_4vEa-Xhe5ikMt0yvs0Zs2i5flXWHMzwGflyAsL_dJ53tHERRwYkVRh9AI"
SHOP_CIPHER = "TTP_uE19hAAAAADx5Flb4Y_fjmWFiQfOEyTT"

SPREADSHEET_ID = "1fVWfictZo6BiKyWO-eFfSo3fAVscOQMPVg1gqa5oMWI"
SHEET_NAME = "Get Order Detail"
SERVICE_ACCOUNT_FILE = "service_account.json"

BASE = "https://open-api.tiktokglobalshop.com"
ORDER_SEARCH_PATH = "/order/202309/orders/search"
ORDER_DETAIL_PATH = "/order/202309/orders"
LA_TZ = ZoneInfo("America/Los_Angeles")

PAGE_SIZE = 50
IDS_PER_CALL = 50
FLUSH_EVERY = 1000
MAX_ORDERS = 60000

HEADERS_ROW = [
    "주문ID", "주문일시(LA)", "결제일시(LA)", "업데이트일시(LA)", "주문상태",
    "구매자닉네임", "구매자이메일", "취소사유", "취소주체",
    "풀필먼트타입", "배송타입", "배송사", "트래킹번호", "창고ID",
    "통화", "총결제금액", "상품소계", "배송비", "셀러할인", "플랫폼할인",
    "세금", "상품세금", "배송비세금", "구매자수수료", "핸들링피",
    "수령인", "전화번호", "우편번호", "지역코드", "전체주소",
    "라인아이템ID", "상품ID", "상품명", "SKU ID", "SKU명", "셀러SKU",
    "정가", "판매가", "라인_셀러할인", "라인_플랫폼할인", "표시상태",
    "패키지ID", "샘플주문", "교환주문", "선물여부",
    "아이템세금(JSON)", "패키지(JSON)",
]


def sign_get(path: str, params: dict) -> str:
    s = APP_SECRET + path
    for k in sorted(params.keys()):
        s += k + str(params[k])
    return hmac.new(APP_SECRET.encode(), (s + APP_SECRET).encode(), hashlib.sha256).hexdigest()


def sign_post(path: str, params: dict, body: str) -> str:
    s = APP_SECRET + path
    for k in sorted(params.keys()):
        s += k + str(params[k])
    s += body
    return hmac.new(APP_SECRET.encode(), (s + APP_SECRET).encode(), hashlib.sha256).hexdigest()


def fetch_order_ids(from_dt: datetime, to_dt: datetime) -> list[str]:
    out: list[str] = []
    page_token = None
    while True:
        body_obj = {"create_time_ge": int(from_dt.timestamp()),
                    "create_time_lt": int(to_dt.timestamp())}
        body = json.dumps(body_obj, separators=(",", ":"))
        params = {"app_key": APP_KEY, "page_size": str(PAGE_SIZE),
                  "shop_cipher": SHOP_CIPHER, "sort_field": "create_time",
                  "sort_order": "ASC", "timestamp": str(int(time.time()))}
        if page_token:
            params["page_token"] = page_token
        qp = dict(params)
        qp["sign"] = sign_post(ORDER_SEARCH_PATH, params, body)
        headers = {"content-type": "application/json",
                   "x-tts-access-token": get_valid_token(ACCESS_TOKEN, REFRESH_TOKEN)}
        try:
            r = requests.post(BASE + ORDER_SEARCH_PATH, params=qp, headers=headers,
                              data=body, timeout=60).json()
        except Exception as e:
            print(f"  [주문목록] 실패: {e}")
            break
        if r.get("code") == 105002:
            handle_token_expired(REFRESH_TOKEN)
            continue
        if r.get("code") != 0:
            print(f"  [주문목록] code={r.get('code')} msg={str(r.get('message'))[:80]}")
            break
        data = r.get("data", {})
        for o in data.get("orders") or []:
            out.append(str(o.get("id", "")))
        nt = data.get("next_page_token") or None
        if not nt or nt == page_token or len(out) >= MAX_ORDERS:
            break
        page_token = nt
        time.sleep(0.15)
    return out


def fetch_details(ids: list[str]) -> list[dict]:
    params = {"app_key": APP_KEY, "shop_cipher": SHOP_CIPHER,
              "ids": ",".join(ids), "timestamp": str(int(time.time()))}
    params["sign"] = sign_get(ORDER_DETAIL_PATH, params)
    url = BASE + ORDER_DETAIL_PATH + "?" + urlencode(params, quote_via=quote)
    headers = {"content-type": "application/json",
               "x-tts-access-token": get_valid_token(ACCESS_TOKEN, REFRESH_TOKEN)}
    for attempt in range(1, 4):
        try:
            d = requests.get(url, headers=headers, timeout=60).json()
            if d.get("code") == 0:
                return d.get("data", {}).get("orders") or []
            if d.get("code") == 105002:
                nt = handle_token_expired(REFRESH_TOKEN)
                if nt:
                    headers["x-tts-access-token"] = nt
                    continue
            print(f"    [상세] code={d.get('code')} msg={str(d.get('message'))[:70]}")
            return []
        except Exception as e:
            print(f"    [상세] 오류 {e} (시도 {attempt}/3)")
            time.sleep(1.5 * attempt)
    return []


def la(ts) -> str:
    try:
        return datetime.fromtimestamp(int(ts), LA_TZ).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return ""


def order_rows(o: dict) -> list[list]:
    pay = o.get("payment") or {}
    addr = o.get("recipient_address") or {}
    base = [
        o.get("id", ""), la(o.get("create_time")), la(o.get("paid_time")),
        la(o.get("update_time")), o.get("status", ""),
        o.get("buyer_nickname", ""), o.get("buyer_email", ""),
        o.get("cancel_reason", ""), o.get("cancellation_initiator", ""),
        o.get("fulfillment_type", ""), o.get("delivery_type", ""),
        o.get("shipping_provider", ""), o.get("tracking_number", ""), o.get("warehouse_id", ""),
        pay.get("currency", ""), pay.get("total_amount", ""), pay.get("sub_total", ""),
        pay.get("shipping_fee", ""), pay.get("seller_discount", ""), pay.get("platform_discount", ""),
        pay.get("tax", ""), pay.get("product_tax", ""), pay.get("shipping_fee_tax", ""),
        pay.get("buyer_service_fee", ""), pay.get("handling_fee", ""),
        addr.get("name", ""), addr.get("phone_number", ""), addr.get("postal_code", ""),
        addr.get("region_code", ""), addr.get("full_address", ""),
    ]
    pkgs = json.dumps(o.get("packages") or [], ensure_ascii=False)[:1000]
    items = o.get("line_items") or []
    if not items:
        return [base + [""] * (len(HEADERS_ROW) - len(base) - 1) + [pkgs]]
    rows = []
    for li in items:
        rows.append(base + [
            li.get("id", ""), li.get("product_id", ""), li.get("product_name", ""),
            li.get("sku_id", ""), li.get("sku_name", ""), li.get("seller_sku", ""),
            li.get("original_price", ""), li.get("sale_price", ""),
            li.get("seller_discount", ""), li.get("platform_discount", ""),
            li.get("display_status", ""), li.get("package_id", ""),
            o.get("is_sample_order", ""), o.get("is_exchange_order", ""), li.get("is_gift", ""),
            json.dumps(li.get("item_tax") or [], ensure_ascii=False)[:1000],
            pkgs,
        ])
    return rows


def flush(sheet, rows: list[list]):
    if not rows:
        return
    for attempt in range(1, 9):
        try:
            sheet.append_rows(rows, value_input_option="USER_ENTERED")
            return
        except Exception as e:
            if attempt == 8:
                raise
            wait = min(3 * attempt, 30)
            print(f"    시트 쓰기 실패 (시도 {attempt}/8), {wait}초 후 재시도... ({e})")
            time.sleep(wait)


def main():
    raw = sys.argv[1] if len(sys.argv) > 1 else "2026-07-01 ~ 2026-08-07"
    nums = re.findall(r"\d{4}-\d{1,2}-\d{1,2}", raw)
    start, end = nums[0], (nums[1] if len(nums) > 1 else nums[0])
    from_dt = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=LA_TZ)
    to_dt = datetime.strptime(end, "%Y-%m-%d").replace(tzinfo=LA_TZ) + timedelta(days=1)
    print(f"\n=== Get Order Detail [{start} ~ {end}] ===")

    print("  [1/2] 주문ID 수집 중...")
    ids = fetch_order_ids(from_dt, to_dt)
    print(f"    총 주문 {len(ids)}건")
    if not ids:
        print("  주문 없음 - 종료")
        return

    print("  [2/2] 주문 상세 조회 + 저장...")
    creds = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"])
    ss = gspread.authorize(creds).open_by_key(SPREADSHEET_ID)
    try:
        sheet = ss.worksheet(SHEET_NAME)
        sheet.clear()
    except gspread.WorksheetNotFound:
        sheet = ss.add_worksheet(title=SHEET_NAME, rows="2000", cols=str(len(HEADERS_ROW)))
    sheet.resize(rows=2000, cols=len(HEADERS_ROW))
    sheet.update([HEADERS_ROW], value_input_option="USER_ENTERED")
    sheet.freeze(rows=1)

    buf: list[list] = []
    total = 0
    for i in range(0, len(ids), IDS_PER_CALL):
        chunk = ids[i:i + IDS_PER_CALL]
        for o in fetch_details(chunk):
            buf.extend(order_rows(o))
        if len(buf) >= FLUSH_EVERY:
            flush(sheet, buf)
            total += len(buf)
            print(f"    진행 {min(i+IDS_PER_CALL, len(ids))}/{len(ids)} 주문 · 누적 {total}행")
            buf = []
        time.sleep(0.15)

    flush(sheet, buf)
    total += len(buf)
    print(f"  ✅ '{SHEET_NAME}' 탭에 총 {total}행 저장 완료")


if __name__ == "__main__":
    main()
