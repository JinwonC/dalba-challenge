"""TikTok Ads API (GMV MAX) → Google Sheets '광고성과' 탭"""
import json
import os
import time
import re
from datetime import datetime, timedelta

import requests
from google.oauth2.service_account import Credentials
import gspread

# ─────────────────────────────────────────
# 설정
# ─────────────────────────────────────────
APP_ID        = "7641873128328101904"
ADVERTISER_ID = "7573855166672355345"
STORE_ID      = "7494221571082258140"

SPREADSHEET_ID       = "1AhVPPUq6Npri72uhtFcOUVMBl1jA7nf2P0qDCDRRKfA"
SHEET_NAME           = "광고성과"
SERVICE_ACCOUNT_FILE = "service_account.json"
TOKEN_FILE           = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_tokens.json")

BASE_URL = "https://business-api.tiktok.com/open_api/v1.3/gmv_max/report/get/"

DIMENSIONS = ["stat_time_day", "campaign_id"]

METRICS = [
    "campaign_name",
    "spend",
    "gross_revenue",
    "orders",
    "roi",
    "impressions",
    "clicks",
    "ctr",
    "cpm",
    "cpc",
    "reach",
    "frequency",
]

HEADERS = [
    "날짜", "캠페인ID", "캠페인명",
    "지출금액", "총매출(GMV)", "주문수", "ROI",
    "노출수", "클릭수", "CTR", "CPM", "CPC",
    "도달수", "빈도",
]


# ─────────────────────────────────────────
# 토큰
# ─────────────────────────────────────────
def get_token() -> str:
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            return json.load(f).get("access_token", "")
    raise FileNotFoundError("ads_tokens.json 없음. get_ads_token.py 먼저 실행하세요.")


# ─────────────────────────────────────────
# 날짜 입력
# ─────────────────────────────────────────
def parse_date_range(raw: str):
    nums = re.findall(r"\d{4}[-./]\d{1,2}[-./]\d{1,2}", raw)
    if len(nums) < 2:
        raise ValueError("날짜 형식 오류. 예: 2026-05-01 ~ 2026-05-15")
    def norm(s):
        return re.sub(r"[./]", "-", s)
    return norm(nums[0]), norm(nums[1])


# ─────────────────────────────────────────
# API 호출
# ─────────────────────────────────────────
def fetch_page(token: str, start_date: str, end_date: str, page: int) -> dict | None:
    params = {
        "advertiser_id": ADVERTISER_ID,
        "store_ids": json.dumps([STORE_ID]),
        "dimensions": json.dumps(DIMENSIONS),
        "metrics": json.dumps(METRICS),
        "start_date": start_date,
        "end_date": end_date,
        "page": page,
        "page_size": 1000,
    }
    for attempt in range(1, 4):
        try:
            resp = requests.get(
                BASE_URL,
                headers={"Access-Token": token},
                params=params,
                timeout=30
            )
            data = resp.json()
            if data.get("code") == 0:
                return data
            print(f"  [경고] code={data.get('code')}, msg={data.get('message')} (시도 {attempt}/3)")
            if data.get("code") in (40002, 40100):
                return None
        except Exception as e:
            print(f"  [오류] {e} (시도 {attempt}/3)")
        time.sleep(2 * attempt)
    return None


def fetch_all(token: str, start_date: str, end_date: str) -> list[list]:
    all_rows = []
    page = 1
    while True:
        print(f"  페이지 {page} 요청 중...")
        result = fetch_page(token, start_date, end_date, page)
        if not result:
            break

        page_info = result.get("data", {}).get("page_info", {})
        rows_data = result.get("data", {}).get("list", [])

        for item in rows_data:
            dims = item.get("dimensions", {})
            mets = item.get("metrics", {})
            all_rows.append([
                dims.get("stat_time_day", "")[:10],
                dims.get("campaign_id", ""),
                mets.get("campaign_name", ""),
                mets.get("spend", ""),
                mets.get("gross_revenue", ""),
                mets.get("orders", ""),
                mets.get("roi", ""),
                mets.get("impressions", ""),
                mets.get("clicks", ""),
                mets.get("ctr", ""),
                mets.get("cpm", ""),
                mets.get("cpc", ""),
                mets.get("reach", ""),
                mets.get("frequency", ""),
            ])

        total_page = page_info.get("total_page", 1)
        if page >= total_page:
            break
        page += 1
        time.sleep(0.3)

    return all_rows


# ─────────────────────────────────────────
# Google Sheets
# ─────────────────────────────────────────
def get_sheet():
    creds = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"]
    )
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


def save(rows: list[list]):
    if not rows:
        print("  저장할 데이터 없음")
        return
    sheet = get_sheet()
    existing = sheet.row_values(1)
    if not existing:
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


# ─────────────────────────────────────────
# 메인
# ─────────────────────────────────────────
def main():
    raw = input("기간 입력 (예: 2026-05-01 ~ 2026-05-15): ").strip()
    start_date, end_date = parse_date_range(raw)
    print(f"\n=== TikTok GMV MAX 광고 성과 [{start_date} ~ {end_date}] ===")

    token = get_token()
    rows = fetch_all(token, start_date, end_date)
    print(f"  총 {len(rows)}행 수집")
    save(rows)


if __name__ == "__main__":
    main()
