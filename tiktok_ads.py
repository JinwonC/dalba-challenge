"""TikTok Ads API → Google Sheets '광고성과' 탭"""
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
APP_ID       = "7641873128328101904"
ADVERTISER_ID = "7573855166672355345"

SPREADSHEET_ID      = "1AhVPPUq6Npri72uhtFcOUVMBl1jA7nf2P0qDCDRRKfA"
SHEET_NAME          = "광고성과"
SERVICE_ACCOUNT_FILE = "service_account.json"
TOKEN_FILE          = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_tokens.json")

BASE_URL = "https://business-api.tiktok.com/open_api/v1.3/report/integrated/get/"

DIMENSIONS = ["ad_id", "stat_time_day"]

METRICS = [
    "ad_name", "adgroup_name", "campaign_name",
    "spend", "impressions", "clicks", "ctr", "cpm", "cpc",
    "reach", "frequency",
    "video_play_actions", "video_watched_2s", "video_watched_6s",
    "video_views_p25", "video_views_p50", "video_views_p75", "video_views_p100",
    "average_video_play", "average_video_play_per_user",
    "conversion", "cost_per_conversion", "conversion_rate",
    "real_time_conversion", "real_time_cost_per_conversion",
    "onsite_shopping",
]

HEADERS = [
    "날짜", "광고ID", "광고명", "광고그룹명", "캠페인명",
    "지출금액", "노출수", "클릭수", "CTR", "CPM", "CPC",
    "도달수", "빈도",
    "영상재생수", "2초시청", "6초시청",
    "25%시청", "50%시청", "75%시청", "100%시청",
    "평균시청시간", "1인당평균시청시간",
    "전환수", "전환당비용(CPA)", "전환율",
    "실시간전환수", "실시간CPA",
    "온사이트주문수",
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
        "report_type": "BASIC",
        "data_level": "AUCTION_AD",
        "dimensions": json.dumps(DIMENSIONS),
        "metrics": json.dumps(METRICS),
        "start_date": start_date,
        "end_date": end_date,
        "page": page,
        "page_size": 1000,
        "lifetime": "false",
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
                dims.get("ad_id", ""),
                mets.get("ad_name", ""),
                mets.get("adgroup_name", ""),
                mets.get("campaign_name", ""),
                mets.get("spend", ""),
                mets.get("impressions", ""),
                mets.get("clicks", ""),
                mets.get("ctr", ""),
                mets.get("cpm", ""),
                mets.get("cpc", ""),
                mets.get("reach", ""),
                mets.get("frequency", ""),
                mets.get("video_play_actions", ""),
                mets.get("video_watched_2s", ""),
                mets.get("video_watched_6s", ""),
                mets.get("video_views_p25", ""),
                mets.get("video_views_p50", ""),
                mets.get("video_views_p75", ""),
                mets.get("video_views_p100", ""),
                mets.get("average_video_play", ""),
                mets.get("average_video_play_per_user", ""),
                mets.get("conversion", ""),
                mets.get("cost_per_conversion", ""),
                mets.get("conversion_rate", ""),
                mets.get("real_time_conversion", ""),
                mets.get("real_time_cost_per_conversion", ""),
                mets.get("onsite_shopping", ""),
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
    for attempt in range(1, 6):
        try:
            sheet.append_rows(rows, value_input_option="USER_ENTERED")
            print(f"  ✅ {len(rows)}행 저장 완료")
            return
        except Exception as e:
            if attempt == 5:
                raise
            print(f"  시트 쓰기 실패 (시도 {attempt}/5), 재시도 중...")
            time.sleep(3 * attempt)


# ─────────────────────────────────────────
# 메인
# ─────────────────────────────────────────
def main():
    raw = input("기간 입력 (예: 2026-05-01 ~ 2026-05-15): ").strip()
    start_date, end_date = parse_date_range(raw)
    print(f"\n=== TikTok Ads 성과 [{start_date} ~ {end_date}] ===")

    token = get_token()
    rows = fetch_all(token, start_date, end_date)
    print(f"  총 {len(rows)}행 수집")
    save(rows)


if __name__ == "__main__":
    main()
