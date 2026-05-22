"""SKU별 성과 → Google Sheets '(중요) SKU Order' 탭"""
from _공통 import call_api, write_to_sheet, SERVICE_ACCOUNT_FILE
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials
import gspread, re, sys

SPREADSHEET_ID = "15dP91bH_skc7ZzcJ3ehH9H4IKCzSxcfuOcREr3OaL0o"
SHEET_NAME = "(중요) SKU Order"
PATH = "/analytics/202509/shop_skus/performance"

HEADERS = ["날짜", "상품ID", "SKU ID", "SKU주문수", "판매수량", "GMV", "통화"]


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


def run(date_str: str):
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
            all_rows.append([
                date_str,
                item.get("product_id") or "",
                item.get("id") or "",
                item.get("sku_orders") or "",
                item.get("units_sold") or "",
                gmv.get("amount") or "",
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
    sheet = get_target_sheet()

    current = datetime.strptime(start_str, "%Y-%m-%d")
    end = datetime.strptime(end_str, "%Y-%m-%d")

    total = 0
    while current <= end:
        date_str = current.strftime("%Y-%m-%d")
        print(f"\n=== SKU별 성과 [{date_str}] ===")
        rows = run(date_str)
        if rows:
            write_to_sheet(sheet, HEADERS, rows)
            total += len(rows)
        else:
            print("  데이터 없음")
        current += timedelta(days=1)

    print(f"\n총 {total}행 저장 완료")
