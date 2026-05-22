"""SKU별 성과 → Google Sheets '(중요) SKU Order' 탭"""
from _공통 import call_api, write_to_sheet, get_date_input, SERVICE_ACCOUNT_FILE
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials
import gspread

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


def run(date_str: str):
    print(f"\n=== SKU별 성과 [{date_str}] ===")
    sheet = get_target_sheet()

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
        items = data.get("skus") or []

        for item in items:
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

    write_to_sheet(sheet, HEADERS, all_rows)

if __name__ == "__main__":
    run(get_date_input())
