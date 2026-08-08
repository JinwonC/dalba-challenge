"""TikTok Shop 주문별 상세 (finance + price detail)
→ 스프레드시트 1fVWfi... 의 두 탭
   - 'Get Transactions by Order' : SKU 단위 정산/수수료/세금 내역
   - 'Get Price Detail'          : 주문/라인아이템 단위 가격 계산 내역

주문ID를 한 번만 수집한 뒤, 주문당 두 API를 함께 호출한다.
경로는 후보 자동 탐색, 주문일시 오름차순, 배치 append 저장.
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
SHEET_NAME = "Get Transactions by Order"
SERVICE_ACCOUNT_FILE = "service_account.json"

BASE = "https://open-api.tiktokglobalshop.com"
ORDER_PATH = "/order/202309/orders/search"
LA_TZ = ZoneInfo("America/Los_Angeles")

PAGE_SIZE = 50
MAX_ORDERS = 60000
FLUSH_EVERY = 1000  # 이 행수마다 시트에 append

# Get Transactions by Order 경로 후보 (문서 경로 미확인 → 자동 탐색)
TX_PATH_TEMPLATES = [
    "/finance/202309/orders/{oid}/statement_transactions",
    "/finance/202501/orders/{oid}/statement_transactions",
    "/finance/202409/orders/{oid}/statement_transactions",
    "/finance/202309/orders/{oid}/transactions",
    "/finance/202501/orders/{oid}/transactions",
]

HEADERS_ROW = [
    "주문ID", "주문일시(LA)", "통화",
    "주문_매출액", "주문_수수료및세금", "주문_배송비", "주문_정산액",
    "SKU ID", "SKU명", "상품명", "statement_id", "수량",
    "SKU_정산액", "SKU_매출액", "SKU_배송비", "SKU_수수료세금",
    "매출상세(JSON)", "배송비상세(JSON)", "수수료상세(JSON)", "세금상세(JSON)",
]

PRICE_SHEET_NAME = "Get Price Detail"

# Get Price Detail 경로 후보
PRICE_PATH_TEMPLATES = [
    "/order/202407/orders/{oid}/price_detail",
    "/order/202309/orders/{oid}/price_detail",
    "/order/202501/orders/{oid}/price_detail",
    "/order/202406/orders/{oid}/price_detail",
]

# 가격 상세에서 뽑을 금액 필드 (주문/라인아이템 공통)
PRICE_FIELDS = [
    "currency", "total", "payment", "sku_list_price", "sku_sale_price",
    "subtotal", "subtotal_deduction_seller", "subtotal_deduction_platform",
    "subtotal_tax_amount", "voucher_deduction_platform", "voucher_deduction_seller",
    "shipping_list_price", "shipping_sale_price",
    "shipping_fee_deduction_seller", "shipping_fee_deduction_platform",
    "shipping_fee_deduction_platform_voucher",
    "tax_amount", "tax_rate", "net_price_amount",
    "cod_fee", "cod_fee_net_amount", "sku_gift_original_price", "sku_gift_net_price",
    "distance_shipping_fee", "distance_fee",
]

PRICE_HEADERS = ["주문ID", "주문일시(LA)", "구분", "라인아이템ID"] + PRICE_FIELDS


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


def api_get(path: str, extra: dict, silent: bool = False):
    params = {"app_key": APP_KEY, "shop_cipher": SHOP_CIPHER,
              "timestamp": str(int(time.time())), **extra}
    params["sign"] = sign_get(path, params)
    url = BASE + path + "?" + urlencode(params, quote_via=quote)
    headers = {"content-type": "application/json",
               "x-tts-access-token": get_valid_token(ACCESS_TOKEN, REFRESH_TOKEN)}
    for attempt in range(1, 4):
        try:
            d = requests.get(url, headers=headers, timeout=30).json()
            if d.get("code") == 0:
                return d
            if d.get("code") == 105002:
                nt = handle_token_expired(REFRESH_TOKEN)
                if nt:
                    headers["x-tts-access-token"] = nt
                    continue
            return d  # 오류 코드 그대로 반환 (탐색/판정용)
        except Exception as e:
            if not silent:
                print(f"    [오류] {e} (시도 {attempt}/3)")
            time.sleep(1.5 * attempt)
    return None


def fetch_order_ids(from_dt: datetime, to_dt: datetime) -> list[tuple[str, int]]:
    """(order_id, create_time) 목록 — create_time 오름차순."""
    out: list[tuple[str, int]] = []
    page_token = None
    page = 0
    while True:
        page += 1
        body_obj = {"create_time_ge": int(from_dt.timestamp()),
                    "create_time_lt": int(to_dt.timestamp())}
        body = json.dumps(body_obj, separators=(",", ":"))
        params = {"app_key": APP_KEY, "page_size": str(PAGE_SIZE),
                  "shop_cipher": SHOP_CIPHER, "sort_field": "create_time",
                  "sort_order": "ASC", "timestamp": str(int(time.time()))}
        if page_token:
            params["page_token"] = page_token
        qp = dict(params)
        qp["sign"] = sign_post(ORDER_PATH, params, body)
        headers = {"content-type": "application/json",
                   "x-tts-access-token": get_valid_token(ACCESS_TOKEN, REFRESH_TOKEN)}
        try:
            r = requests.post(BASE + ORDER_PATH, params=qp, headers=headers,
                              data=body, timeout=60).json()
        except Exception as e:
            print(f"  [주문목록] 요청 실패: {e}")
            break
        if r.get("code") == 105002:
            handle_token_expired(REFRESH_TOKEN)
            continue
        if r.get("code") != 0:
            print(f"  [주문목록] code={r.get('code')} msg={str(r.get('message'))[:80]}")
            break
        data = r.get("data", {})
        for o in data.get("orders") or []:
            out.append((str(o.get("id", "")), int(o.get("create_time") or 0)))
        if page % 20 == 0:
            print(f"    ...주문 {len(out)}건 수집")
        nt = data.get("next_page_token") or None
        if not nt or nt == page_token or len(out) >= MAX_ORDERS:
            break
        page_token = nt
        time.sleep(0.15)
    out.sort(key=lambda x: x[1])
    return out


def probe_tx_path(sample_oid: str) -> str | None:
    for tpl in TX_PATH_TEMPLATES:
        path = tpl.format(oid=sample_oid)
        d = api_get(path, {}, silent=True)
        code = d.get("code") if d else None
        print(f"  probe {tpl} → code={code} msg={str(d.get('message'))[:70] if d else '-'}")
        if code == 0:
            return tpl
        time.sleep(0.2)
    return None


def probe_price_path(sample_oid: str) -> str | None:
    for tpl in PRICE_PATH_TEMPLATES:
        path = tpl.format(oid=sample_oid)
        d = api_get(path, {}, silent=True)
        code = d.get("code") if d else None
        print(f"  probe {tpl} → code={code} msg={str(d.get('message'))[:70] if d else '-'}")
        if code == 0:
            return tpl
        time.sleep(0.2)
    return None


def la(ts) -> str:
    try:
        return datetime.fromtimestamp(int(ts), LA_TZ).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return ""


def get_sheet(ss, name: str, headers: list[str]):
    try:
        sheet = ss.worksheet(name)
        sheet.clear()
    except gspread.WorksheetNotFound:
        sheet = ss.add_worksheet(title=name, rows="2000", cols=str(len(headers)))
    sheet.resize(rows=2000, cols=len(headers))
    sheet.update([headers], value_input_option="USER_ENTERED")
    sheet.freeze(rows=1)
    return sheet


def open_spreadsheet():
    creds = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds).open_by_key(SPREADSHEET_ID)


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
    raw = sys.argv[1] if len(sys.argv) > 1 else "2026-01-01 ~ 2026-08-07"
    nums = re.findall(r"\d{4}-\d{1,2}-\d{1,2}", raw)
    start, end = nums[0], (nums[1] if len(nums) > 1 else nums[0])
    from_dt = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=LA_TZ)
    to_dt = datetime.strptime(end, "%Y-%m-%d").replace(tzinfo=LA_TZ) + timedelta(days=1)
    print(f"\n=== Get Transactions by Order [{start} ~ {end}] ===")

    print("  [1/3] 주문ID 수집 중...")
    orders = fetch_order_ids(from_dt, to_dt)
    print(f"    총 주문 {len(orders)}건")
    if not orders:
        print("  주문 없음 - 종료")
        return

    print("  [2/3] 엔드포인트 탐색...")
    tx_tpl = probe_tx_path(orders[0][0])
    price_tpl = probe_price_path(orders[0][0])
    if not tx_tpl and not price_tpl:
        print("  ❌ 두 엔드포인트 모두 확인 실패 — 문서 경로 확인 필요")
        sys.exit(1)
    print(f"    거래내역: {tx_tpl or '미확인(건너뜀)'}")
    print(f"    가격상세: {price_tpl or '미확인(건너뜀)'}")

    print("  [3/3] 주문별 조회 + 시트 저장...")
    ss = open_spreadsheet()
    tx_sheet = get_sheet(ss, SHEET_NAME, HEADERS_ROW) if tx_tpl else None
    price_sheet = get_sheet(ss, PRICE_SHEET_NAME, PRICE_HEADERS) if price_tpl else None
    tx_buf: list[list] = []
    price_buf: list[list] = []
    tx_total = price_total = 0

    for i, (oid, ct) in enumerate(orders, 1):
        when = la(ct)
        # --- 거래내역 ---
        if tx_tpl:
            d = api_get(tx_tpl.format(oid=oid), {}, silent=True)
            if d and d.get("code") == 0:
                t = d.get("data") or {}
                base = [oid, when, t.get("currency", ""),
                        t.get("revenue_amount", ""), t.get("fee_and_tax_amount", ""),
                        t.get("shipping_cost_amount", ""), t.get("settlement_amount", "")]
                skus = t.get("sku_transactions") or []
                if not skus:
                    tx_buf.append(base + [""] * (len(HEADERS_ROW) - len(base)))
                for s in skus:
                    fee_tax = s.get("fee_tax_breakdown") or {}
                    tx_buf.append(base + [
                        s.get("sku_id", ""), s.get("sku_name", ""), s.get("product_name", ""),
                        s.get("statement_id", ""), s.get("quantity", ""),
                        s.get("settlement_amount", ""), s.get("revenue_amount", ""),
                        s.get("shipping_cost_amount", ""), s.get("fee_tax_amount", ""),
                        json.dumps(s.get("revenue_breakdown") or {}, ensure_ascii=False)[:2000],
                        json.dumps(s.get("shipping_cost_breakdown") or {}, ensure_ascii=False)[:2000],
                        json.dumps(fee_tax.get("fee") or {}, ensure_ascii=False)[:5000],
                        json.dumps(fee_tax.get("tax") or {}, ensure_ascii=False)[:2000],
                    ])
        # --- 가격 상세 ---
        if price_tpl:
            d = api_get(price_tpl.format(oid=oid), {}, silent=True)
            if d and d.get("code") == 0:
                p = d.get("data") or {}
                price_buf.append([oid, when, "ORDER", ""] + [p.get(f, "") for f in PRICE_FIELDS])
                for li in p.get("line_items") or []:
                    price_buf.append([oid, when, "LINE_ITEM", li.get("id", "")]
                                     + [li.get(f, "") for f in PRICE_FIELDS])

        if len(tx_buf) >= FLUSH_EVERY:
            flush(tx_sheet, tx_buf); tx_total += len(tx_buf); tx_buf = []
        if len(price_buf) >= FLUSH_EVERY:
            flush(price_sheet, price_buf); price_total += len(price_buf); price_buf = []
        if i % 500 == 0:
            print(f"    진행 {i}/{len(orders)} 주문 · 거래 {tx_total}행 / 가격 {price_total}행")
        time.sleep(0.08)

    if tx_sheet:
        flush(tx_sheet, tx_buf); tx_total += len(tx_buf)
        print(f"  ✅ '{SHEET_NAME}' 탭 {tx_total}행 저장 완료")
    if price_sheet:
        flush(price_sheet, price_buf); price_total += len(price_buf)
        print(f"  ✅ '{PRICE_SHEET_NAME}' 탭 {price_total}행 저장 완료")


if __name__ == "__main__":
    main()
