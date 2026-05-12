"""
TikTok Shop 상품별 일별 성과 로그 → Google Sheets (Python)
날짜를 직접 입력하면 해당 날짜 데이터를 가져옵니다.
"""

import hashlib
import hmac
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, quote

import requests
from google.oauth2.service_account import Credentials
import gspread

# ─────────────────────────────────────────
# 설정값
# ─────────────────────────────────────────
APP_KEY = "6jd7l2nu36rd4"
APP_SECRET = "9ab6f9c3467d53c72ca6e346c18b8071338f0ce4"
ACCESS_TOKEN = "TTP_mn2IxwAAAAAKxe5s-tyxQjFx-BLmHCzEUHx_N8KtbJs8REguA-PlojAyV0wGbdEfcH65GTeVkz7R1pOu5g44xImqf4SrMwS1lO9DYpNMbWgm0cWkq23XF2YLKNYP0Q9AWsQoqwJr7vXYF-ZqwGImOOFyM8PZAxutDVhpkZrj-VwpotDYlw_kig"
SHOP_CIPHER = "TTP_uE19hAAAAADx5Flb4Y_fjmWFiQfOEyTT"
SHEET_NAME = "상품별_일별_로그"

SPREADSHEET_ID = "1wGM9UFdFMtXZtm2TQUsuUsQQZkREYBB4Q8okuIqC3UU"
SERVICE_ACCOUNT_FILE = "service_account.json"

HEADERS = ["날짜", "PID", "상품명", "조회수", "GPM"]


# ─────────────────────────────────────────
# TikTok 서명 / 요청
# ─────────────────────────────────────────

def compute_hmac_sha256(message: str, secret: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


def make_tiktok_sign(path: str, params: dict) -> str:
    sorted_keys = sorted(params.keys())
    sign_str = APP_SECRET + path
    for key in sorted_keys:
        sign_str += key + str(params[key])
    sign_str += APP_SECRET
    return compute_hmac_sha256(sign_str, APP_SECRET)


def fetch_video_data(start_date_str: str, end_date_str: str, page_token: str | None = None) -> dict | None:
    timestamp = str(int(time.time()))
    path = "/analytics/202409/shop_videos/performance"

    params = {
        "account_type": "ALL",
        "app_key": APP_KEY,
        "currency": "USD",
        "end_date_lt": end_date_str,
        "page_size": "100",
        "shop_cipher": SHOP_CIPHER,
        "start_date_ge": start_date_str,
        "timestamp": timestamp,
    }
    if page_token:
        params["page_token"] = page_token

    params["sign"] = make_tiktok_sign(path, params)

    url = "https://open-api.tiktokglobalshop.com" + path + "?" + urlencode(params, quote_via=quote)
    headers = {
        "x-tts-access-token": ACCESS_TOKEN,
        "content-type": "application/json",
    }

    for attempt in range(1, 4):
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            data = resp.json()
            if data.get("code") == 0:
                return data
            print(f"  [경고] API code={data.get('code')}, msg={data.get('message')} (시도 {attempt}/3)")
        except Exception as e:
            print(f"  [오류] {e} (시도 {attempt}/3)")
        time.sleep(2 * attempt)

    return None


# ─────────────────────────────────────────
# Google Sheets 연결
# ─────────────────────────────────────────

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


# ─────────────────────────────────────────
# 메인 동기화 로직
# ─────────────────────────────────────────

def sync_daily_log(target_date_str: str):
    """
    target_date_str: "2026-05-01" 형식
    """
    target_date = datetime.strptime(target_date_str, "%Y-%m-%d")
    next_date = target_date + timedelta(days=1)
    end_date_str = next_date.strftime("%Y-%m-%d")

    print(f"\n=== 상품별 일별 성과 수집 시작 ===")
    print(f"대상 날짜: {target_date_str}")

    sheet = get_sheet()

    page_token = None
    page_count = 0
    pid_stats: dict[str, dict] = {}

    while True:
        print(f"  페이지 {page_count + 1} 요청 중...")
        result = fetch_video_data(target_date_str, end_date_str, page_token)

        if not result:
            print("  API 오류 - 중단")
            break

        videos = result.get("data", {}).get("videos") or []

        for video in videos:
            products = video.get("products") or []
            views = video.get("views") or 0
            gpm_data = video.get("gpm") or {}
            video_gpm = float(gpm_data.get("amount") or 0)

            for product in products:
                pid = str(product.get("id") or "")
                if not pid:
                    continue
                if pid not in pid_stats:
                    pid_stats[pid] = {"name": product.get("name") or "", "total_views": 0, "gpm_sum": 0.0, "video_count": 0}
                pid_stats[pid]["total_views"] += views
                pid_stats[pid]["gpm_sum"] += video_gpm
                pid_stats[pid]["video_count"] += 1

        new_token = result.get("data", {}).get("next_page_token") or None
        if not new_token or new_token == page_token:
            break
        page_token = new_token
        page_count += 1
        time.sleep(0.3)

    if not pid_stats:
        print("  수집된 데이터가 없습니다.")
        return

    rows = []
    for pid, stat in pid_stats.items():
        avg_gpm = round(stat["gpm_sum"] / stat["video_count"], 2) if stat["video_count"] > 0 else 0
        rows.append([target_date_str, pid, stat["name"], stat["total_views"], avg_gpm])

    # 시트에 추가
    for attempt in range(1, 6):
        try:
            sheet.append_rows(rows, value_input_option="USER_ENTERED")
            break
        except Exception as e:
            if attempt == 5:
                raise
            print(f"  시트 쓰기 실패 (시도 {attempt}/5), 재시도 중...")
            time.sleep(3 * attempt)

    print(f"\n✅ 완료! {target_date_str} / {len(rows)}개 상품 기록됨 (총 {page_count + 1}페이지)")


# ─────────────────────────────────────────
# 실행
# ─────────────────────────────────────────

if __name__ == "__main__":
    date_input = input("날짜 입력 (예: 2026-05-01): ").strip()
    try:
        datetime.strptime(date_input, "%Y-%m-%d")
    except ValueError:
        print("날짜 형식이 잘못됐습니다. yyyy-MM-dd 형식으로 입력해주세요.")
        exit(1)

    sync_daily_log(date_input)
