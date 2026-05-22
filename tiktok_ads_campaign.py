"""TikTok GMV MAX 캠페인별 성과 → Google Sheets '광고성과' 탭"""
import json, os, time, re
import requests
from google.oauth2.service_account import Credentials
import gspread

ADVERTISER_ID        = "7573855166672355345"
STORE_ID             = "7494221571082258140"
SPREADSHEET_ID       = "1AhVPPUq6Npri72uhtFcOUVMBl1jA7nf2P0qDCDRRKfA"
SHEET_NAME           = "광고성과"
SERVICE_ACCOUNT_FILE = "service_account.json"
TOKEN_FILE           = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_tokens.json")
BASE_URL             = "https://business-api.tiktok.com/open_api/v1.3/gmv_max/report/get/"

HEADERS = ["날짜", "캠페인ID", "지출금액", "주문수", "총매출(GMV)", "ROI"]


def get_token():
    with open(TOKEN_FILE) as f:
        return json.load(f)["access_token"]


def parse_date_range(raw):
    nums = re.findall(r"\d{4}[-./]\d{1,2}[-./]\d{1,2}", raw)
    if len(nums) < 2:
        raise ValueError("날짜 형식 오류. 예: 2026-05-01 ~ 2026-05-15")
    return [re.sub(r"[./]", "-", s) for s in nums[:2]]


def fetch_all(token, start_date, end_date):
    rows, page = [], 1
    while True:
        print(f"  페이지 {page} 요청 중...")
        for attempt in range(1, 4):
            try:
                r = requests.get(BASE_URL, headers={"Access-Token": token}, params={
                    "advertiser_id": ADVERTISER_ID,
                    "store_ids": json.dumps([STORE_ID]),
                    "dimensions": json.dumps(["stat_time_day", "campaign_id"]),
                    "metrics": json.dumps(["cost", "orders", "gross_revenue", "roi"]),
                    "start_date": start_date, "end_date": end_date,
                    "page": page, "page_size": 1000,
                }, timeout=30)
                d = r.json()
                if d.get("code") == 0:
                    for item in d["data"]["list"]:
                        dims, mets = item["dimensions"], item["metrics"]
                        rows.append([
                            dims["stat_time_day"][:10],
                            dims["campaign_id"],
                            mets["cost"], mets["orders"],
                            mets["gross_revenue"], mets["roi"],
                        ])
                    if page >= d["data"]["page_info"]["total_page"]:
                        return rows
                    page += 1
                    time.sleep(0.3)
                    break
                print(f"  [경고] code={d.get('code')}, msg={d.get('message')} (시도 {attempt}/3)")
            except Exception as e:
                print(f"  [오류] {e} (시도 {attempt}/3)")
            time.sleep(2 * attempt)
        else:
            return rows


def save(rows):
    if not rows:
        print("  저장할 데이터 없음")
        return
    creds = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"]
    )
    spreadsheet = gspread.authorize(creds).open_by_key(SPREADSHEET_ID)
    try:
        sheet = spreadsheet.worksheet(SHEET_NAME)
    except gspread.WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title=SHEET_NAME, rows="5000", cols=str(len(HEADERS)))
        sheet.append_row(HEADERS)
        sheet.freeze(rows=1)
        print(f"  시트 '{SHEET_NAME}' 새로 생성됨")
    if not sheet.row_values(1):
        sheet.append_row(HEADERS)
        sheet.freeze(rows=1)
    for attempt in range(1, 9):
        try:
            sheet.append_rows(rows, value_input_option="USER_ENTERED")
            print(f"  ✅ {len(rows)}행 저장 완료")
            return
        except Exception as e:
            if attempt == 8:
                raise
            wait = min(3 * attempt, 30)
            print(f"  시트 쓰기 실패 (시도 {attempt}/8), {wait}초 후 재시도...")
            time.sleep(wait)


def main():
    raw = input("기간 입력 (예: 2026-05-01 ~ 2026-05-15): ").strip()
    start_date, end_date = parse_date_range(raw)
    print(f"\n=== TikTok GMV MAX 광고성과 [{start_date} ~ {end_date}] ===")
    token = get_token()
    rows = fetch_all(token, start_date, end_date)
    print(f"  총 {len(rows)}행 수집")
    save(rows)


if __name__ == "__main__":
    main()
