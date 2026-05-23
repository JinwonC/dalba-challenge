"""TikTok Shop 상품 전체 목록 → Google Sheets '상품목록' 탭
상품ID, 상품명, SKU ID, SKU명, 판매가, 재고 저장
"""
import hashlib, hmac, json, os, time
from urllib.parse import urlencode, quote
import requests
from google.oauth2.service_account import Credentials
import gspread
from _공통 import (
    APP_KEY, APP_SECRET, SHOP_CIPHER, SERVICE_ACCOUNT_FILE,
    get_current_token, refresh_token_if_needed
)

SPREADSHEET_ID = "15dP91bH_skc7ZzcJ3ehH9H4IKCzSxcfuOcREr3OaL0o"
SHEET_NAME     = "상품목록"
BASE_URL       = "https://open-api.tiktokglobalshop.com"
PATH           = "/product/202309/products/search"

HEADERS = ["상품ID", "상품명", "SKU ID", "SKU명", "판매가", "통화", "재고"]


def make_post_sign(path, params, body):
    keys = sorted(params.keys())
    s = APP_SECRET + path
    for k in keys:
        s += k + str(params[k])
    s += body + APP_SECRET
    return hmac.new(APP_SECRET.encode(), s.encode(), hashlib.sha256).hexdigest()


def call_post(body_obj, page_token=None):
    body_obj = {**body_obj}
    if page_token:
        body_obj["page_token"] = page_token
    body_str = json.dumps(body_obj, separators=(",", ":"))

    for attempt in range(1, 4):
        ts = str(int(time.time()))
        params = {"app_key": APP_KEY, "shop_cipher": SHOP_CIPHER, "timestamp": ts}
        params["sign"] = make_post_sign(PATH, params, body_str)
        url = BASE_URL + PATH + "?" + urlencode(params, quote_via=quote)
        hdrs = {"x-tts-access-token": get_current_token(), "content-type": "application/json"}
        try:
            r = requests.post(url, headers=hdrs, data=body_str, timeout=30)
            d = r.json()
            if d.get("code") == 0:
                return d
            if d.get("code") == 105002:
                print("  [토큰 만료] 자동 갱신 중...")
                refresh_token_if_needed()
                continue
            print(f"  [경고] code={d.get('code')}, msg={d.get('message')} (시도 {attempt}/3)")
        except Exception as e:
            print(f"  [오류] {e} (시도 {attempt}/3)")
        time.sleep(2 * attempt)
    return None


def fetch_all_products():
    rows = []
    page_token = None
    page = 1

    while True:
        print(f"  페이지 {page} 조회 중...")
        result = call_post({"page_size": 100}, page_token)
        if not result:
            break

        products = (result.get("data") or {}).get("products") or []
        for p in products:
            pid   = str(p.get("id") or "")
            pname = p.get("title") or p.get("name") or ""
            skus  = p.get("skus") or []
            if skus:
                for sku in skus:
                    sid     = str(sku.get("id") or "")
                    sname   = sku.get("seller_sku") or ""
                    price   = (sku.get("price") or {})
                    amount  = price.get("sale_price") or price.get("original_price") or ""
                    currency = price.get("currency") or "USD"
                    stock   = sum(
                        (w.get("available_quantity") or 0)
                        for w in (sku.get("inventory") or [])
                    )
                    rows.append(["'" + pid, pname, "'" + sid, sname, amount, currency, stock])
            else:
                rows.append(["'" + pid, pname, "", "", "", "USD", ""])

        next_token = (result.get("data") or {}).get("next_page_token") or ""
        if not next_token or next_token == page_token:
            break
        page_token = next_token
        page += 1
        time.sleep(0.3)

    return rows


def main():
    print("=== TikTok Shop 상품 목록 수집 ===")
    rows = fetch_all_products()
    print(f"  총 {len(rows)}행 수집")

    if not rows:
        print("  데이터 없음")
        return

    creds = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"]
    )
    spreadsheet = gspread.authorize(creds).open_by_key(SPREADSHEET_ID)
    try:
        sheet = spreadsheet.worksheet(SHEET_NAME)
        sheet.clear()
    except gspread.WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title=SHEET_NAME, rows="5000", cols="10")
        print(f"  시트 '{SHEET_NAME}' 새로 생성됨")

    sheet.append_row(HEADERS)
    sheet.freeze(rows=1)
    for attempt in range(1, 6):
        try:
            sheet.append_rows(rows, value_input_option="USER_ENTERED")
            print(f"  ✅ {len(rows)}행 저장 완료 → '{SHEET_NAME}'")
            return
        except Exception as e:
            if attempt == 5:
                raise
            wait = min(3 * attempt, 30)
            print(f"  시트 쓰기 실패 (시도 {attempt}/5), {wait}초 후 재시도...")
            time.sleep(wait)


if __name__ == "__main__":
    main()
