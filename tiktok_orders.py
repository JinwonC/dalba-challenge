import re
import json
import hmac
import time
import hashlib
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from google.oauth2.service_account import Credentials
import gspread

# =========================
# 1. 기본 설정
# =========================

APP_KEY = "6jd7l2nu36rd4"
APP_SECRET = "9ab6f9c3467d53c72ca6e346c18b8071338f0ce4"
ACCESS_TOKEN = "TTP_mn2IxwAAAAAKxe5s-tyxQjFx-BLmHCzEUHx_N8KtbJs8REguA-PlojAyV0wGbdEfcH65GTeVkz7R1pOu5g44xImqf4SrMwS1lO9DYpNMbWgm0cWkq23XF2YLKNYP0Q9AWsQoqwJr7vXYF-ZqwGImOOFyM8PZAxutDVhpkZrj-VwpotDYlw_kig"
SHOP_CIPHER = "TTP_uE19hAAAAADx5Flb4Y_fjmWFiQfOEyTT"

SPREADSHEET_ID = "1wGM9UFdFMtXZtm2TQUsuUsQQZkREYBB4Q8okuIqC3UU"
SHEET_NAME = "주문데이터"
SERVICE_ACCOUNT_FILE = "service_account.json"

BASE_URL = "https://open-api.tiktokglobalshop.com"
ORDER_PATH = "/order/202309/orders/search"

LA_TZ = ZoneInfo("America/Los_Angeles")

PAGE_SIZE = 50
MAX_RETRIES = 3

HEADERS = [
    "주문번호", "주문일시(LA)", "업데이트일시(LA)", "주문상태", "구매자닉네임", "구매자이메일",
    "상품ID", "상품명", "SKU명", "SKU ID",
    "수량", "정가", "판매가", "셀러할인", "플랫폼할인",
    "소계", "배송비", "세금", "총결제금액", "통화",
    "배송사", "트래킹번호", "배송타입", "풀필먼트타입",
    "결제수단", "결제일시(LA)",
    "수령인이름", "주소", "도시", "주", "우편번호", "국가",
    "샘플주문여부", "교환주문여부"
]


# =========================
# 2. TikTok Shop API 서명
# =========================

def compute_hmac_sha256(message: str, secret: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


def make_sign(path: str, params: dict, body: str) -> str:
    sorted_keys = sorted(params.keys())
    sign_str = APP_SECRET + path
    for key in sorted_keys:
        sign_str += key + str(params[key])
    if body:
        sign_str += body
    sign_str += APP_SECRET
    return compute_hmac_sha256(sign_str, APP_SECRET)


# =========================
# 3. 날짜 입력 파싱
# =========================

def parse_date_range(user_input: str):
    pattern = r"(\d{4})[.-](\d{1,2})[.-](\d{1,2})\s*-\s*(\d{4})[.-](\d{1,2})[.-](\d{1,2})"
    match = re.search(pattern, user_input.strip())
    if not match:
        raise ValueError("날짜 형식이 잘못되었습니다. 예: 2026.04.07 - 2026.04.10")
    y1, m1, d1, y2, m2, d2 = map(int, match.groups())
    from_dt = datetime(y1, m1, d1, 0, 0, 0, tzinfo=LA_TZ)
    to_dt = datetime(y2, m2, d2, 0, 0, 0, tzinfo=LA_TZ) + timedelta(days=1)
    if to_dt <= from_dt:
        raise ValueError("종료일은 시작일보다 같거나 뒤여야 합니다.")
    return from_dt, to_dt


def to_unix_seconds(dt: datetime) -> int:
    return int(dt.timestamp())


def format_la_time(timestamp_value):
    if not timestamp_value:
        return ""
    try:
        dt = datetime.fromtimestamp(int(timestamp_value), tz=LA_TZ)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


# =========================
# 4. 주문 API 호출
# =========================

def fetch_orders_by_date_range(from_dt: datetime, to_dt: datetime, page_token: str | None = None):
    timestamp = str(int(time.time()))
    body_obj = {
        "create_time_ge": to_unix_seconds(from_dt),
        "create_time_lt": to_unix_seconds(to_dt)
    }
    body = json.dumps(body_obj, separators=(",", ":"))
    params = {
        "app_key": APP_KEY,
        "page_size": str(PAGE_SIZE),
        "shop_cipher": SHOP_CIPHER,
        "sort_field": "create_time",
        "sort_order": "ASC",
        "timestamp": timestamp
    }
    if page_token:
        params["page_token"] = page_token

    sign = make_sign(ORDER_PATH, params, body)
    query_params = params.copy()
    query_params["sign"] = sign

    headers = {
        "x-tts-access-token": ACCESS_TOKEN,
        "content-type": "application/json"
    }

    url = BASE_URL + ORDER_PATH
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.post(url, params=query_params, headers=headers, data=body, timeout=60)
            try:
                result = response.json()
            except Exception:
                raise RuntimeError(f"JSON 파싱 실패: {response.text[:500]}")
            if result.get("code") == 0:
                return result
            last_error = result
            print(f"[재시도 {attempt}/{MAX_RETRIES}] API 에러:", result.get("message"), result.get("code"))
            time.sleep(2 * attempt)
        except Exception as e:
            last_error = str(e)
            print(f"[재시도 {attempt}/{MAX_RETRIES}] 요청 실패:", e)
            time.sleep(2 * attempt)

    raise RuntimeError(f"API 호출 실패: {last_error}")


# =========================
# 5. 주문 데이터 평탄화
# =========================

def get_district_name(order: dict, level: str) -> str:
    address = order.get("recipient_address") or {}
    districts = address.get("district_info") or []
    for d in districts:
        if d.get("address_level") == level:
            return d.get("address_name", "")
    return ""


def flatten_orders(orders: list[dict]) -> list[list]:
    rows = []
    for order in orders:
        line_items = order.get("line_items") or []
        for item in line_items:
            payment = order.get("payment") or {}
            address = order.get("recipient_address") or {}
            row = [
                order.get("id", ""),
                format_la_time(order.get("create_time")),
                format_la_time(order.get("update_time")),
                order.get("status", ""),
                order.get("buyer_nickname", ""),
                order.get("buyer_email", ""),
                item.get("product_id", ""),
                item.get("product_name", ""),
                item.get("sku_name", ""),
                item.get("sku_id", ""),
                item.get("quantity", 1),
                item.get("original_price", ""),
                item.get("sale_price", ""),
                item.get("seller_discount", ""),
                item.get("platform_discount", ""),
                payment.get("sub_total", ""),
                payment.get("shipping_fee", ""),
                payment.get("tax", ""),
                payment.get("total_amount", ""),
                payment.get("currency", ""),
                order.get("shipping_provider", ""),
                order.get("tracking_number", ""),
                order.get("delivery_type", ""),
                order.get("fulfillment_type", ""),
                order.get("payment_method_name", ""),
                format_la_time(order.get("paid_time")),
                address.get("name", ""),
                address.get("address_line1", ""),
                get_district_name(order, "L3"),
                get_district_name(order, "L1"),
                address.get("postal_code", ""),
                address.get("region_code", ""),
                "Y" if order.get("is_sample_order") else "N",
                "Y" if order.get("is_exchange_order") else "N"
            ]
            rows.append(row)
    return rows


# =========================
# 6. 전체 페이지 수집
# =========================

def fetch_all_orders(from_dt: datetime, to_dt: datetime) -> list[list]:
    all_rows = []
    page_token = None
    page_count = 0
    seen_keys = set()

    while True:
        result = fetch_orders_by_date_range(from_dt, to_dt, page_token)
        data = result.get("data") or {}
        orders = data.get("orders") or []
        total_count = data.get("total_count", "?")
        print(f"페이지 {page_count + 1} / 주문 {len(orders)}건 / 전체 {total_count}건")

        rows = flatten_orders(orders)
        for row in rows:
            unique_key = f"{row[0]}_{row[9]}"  # 주문번호_SKU ID
            if unique_key in seen_keys:
                continue
            seen_keys.add(unique_key)
            all_rows.append(row)

        next_page_token = data.get("next_page_token")
        if not next_page_token or next_page_token == page_token:
            break
        page_token = next_page_token
        page_count += 1
        time.sleep(0.3)

    return all_rows


# =========================
# 7. Google Sheets 저장
# =========================

def get_sheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SPREADSHEET_ID)

    try:
        sheet = spreadsheet.worksheet(SHEET_NAME)
    except gspread.WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title=SHEET_NAME, rows="1000", cols=str(len(HEADERS)))
        sheet.append_row(HEADERS)
        sheet.freeze(rows=1)
        print(f"  시트 '{SHEET_NAME}' 새로 생성됨")

    return sheet


def save_to_sheets(rows: list[list]):
    if not rows:
        print("저장할 주문 데이터가 없습니다.")
        return

    sheet = get_sheet()

    for attempt in range(1, 6):
        try:
            sheet.append_rows(rows, value_input_option="USER_ENTERED")
            print(f"✅ Google Sheets 저장 완료! {len(rows)}건")
            return
        except Exception as e:
            if attempt == 5:
                raise
            print(f"  시트 쓰기 실패 (시도 {attempt}/5), 재시도 중...")
            time.sleep(3 * attempt)


# =========================
# 8. 메인 실행
# =========================

def main():
    user_input = input("조회할 날짜 범위를 입력하세요. 예: 2026.04.07 - 2026.04.10\n> ")

    from_dt, to_dt = parse_date_range(user_input)

    print("\n조회 기간")
    print("시작:", from_dt.strftime("%Y-%m-%d %H:%M:%S %Z"))
    print("종료:", to_dt.strftime("%Y-%m-%d %H:%M:%S %Z"), "미만\n")

    rows = fetch_all_orders(from_dt, to_dt)

    print(f"\n총 주문 라인 수: {len(rows)}")
    save_to_sheets(rows)


if __name__ == "__main__":
    main()
