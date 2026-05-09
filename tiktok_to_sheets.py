"""
TikTok Shop Video Performance API → Google Sheets (Python)
Apps Script의 6분 실행 제한을 우회하기 위한 Python 버전
"""

import hashlib
import hmac
import json
import math
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, quote

import requests
from google.oauth2.service_account import Credentials
import gspread

# ─────────────────────────────────────────
# 설정값 (Apps Script 상수와 동일)
# ─────────────────────────────────────────
VIDEO_APP_KEY = "6jd7l2nu36rd4"
VIDEO_APP_SECRET = "9ab6f9c3467d53c72ca6e346c18b8071338f0ce4"
VIDEO_ACCESS_TOKEN = "TTP_Tq9f8wAAAAAKxe5s-tyxQjFx-BLmHCzEUHx_N8KtbJs8REguA-PlojAyV0wGbdEfcH65GTeVkz7R1pOu5g44xImqf4SrMwS1Tl3tKGCpcc6aEfyc4bCwpRJfyzCeYQM6gnN8oMMAKMOok9H93mKhVT9RDossLVuroIzI5Gn6WO4OwVzVJZ0g7A"
VIDEO_SHOP_CIPHER = "TTP_uE19hAAAAADx5Flb4Y_fjmWFiQfOEyTT"
VIDEO_CURRENCY = "USD"
VIDEO_ACCOUNT_TYPE = "ALL"
VIDEO_SHEET_NAME = "영상성과데이터"

# Google Sheets 스프레드시트 ID (URL에서 복사)
# 예: https://docs.google.com/spreadsheets/d/xxxxxx/edit → "xxxxxx"
SPREADSHEET_ID = "1_qkd6LZ1wFoihhJSuYdabQ4iRbx-jsFYVxeGIoEb-_g"

# 서비스 계정 JSON 키 파일 경로
SERVICE_ACCOUNT_FILE = "service_account.json"

HEADERS = [
    "Video ID", "포스팅일(LA)", "크리에이터", "제목", "누적 GMV",
    "Currency", "SKU Orders", "Units Sold", "Views", "CTR",
    "Product IDs", "Product Names", "마지막업데이트"
]

LA_TZ = timezone(timedelta(hours=-8))  # America/Los_Angeles (표준시, DST 무시)


# ─────────────────────────────────────────
# TikTok 서명 / 요청 유틸
# ─────────────────────────────────────────

def compute_hmac_sha256(message: str, secret: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


def make_tiktok_sign(path: str, params: dict) -> str:
    sorted_keys = sorted(params.keys())
    sign_str = VIDEO_APP_SECRET + path
    for key in sorted_keys:
        sign_str += key + str(params[key])
    sign_str += VIDEO_APP_SECRET
    return compute_hmac_sha256(sign_str, VIDEO_APP_SECRET)


def fetch_video_performance(start_date: datetime, end_date: datetime, page_token: str | None = None) -> dict | None:
    timestamp = str(int(time.time()))
    path = "/analytics/202409/shop_videos/performance"

    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    params = {
        "account_type": VIDEO_ACCOUNT_TYPE,
        "app_key": VIDEO_APP_KEY,
        "currency": VIDEO_CURRENCY,
        "end_date_lt": end_str,
        "page_size": "100",
        "shop_cipher": VIDEO_SHOP_CIPHER,
        "sort_field": "gmv",
        "sort_order": "DESC",
        "start_date_ge": start_str,
        "timestamp": timestamp,
    }
    if page_token:
        params["page_token"] = page_token

    params["sign"] = make_tiktok_sign(path, params)

    url = "https://open-api.tiktokglobalshop.com" + path + "?" + urlencode(params, quote_via=quote)
    headers = {
        "x-tts-access-token": VIDEO_ACCESS_TOKEN,
        "content-type": "application/json",
    }

    for attempt in range(1, 4):
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            data = resp.json()
            if data.get("code") == 0:
                return data
            print(f"  [경고] API 응답 code={data.get('code')}, msg={data.get('message')} (시도 {attempt}/3)")
        except Exception as e:
            print(f"  [오류] 요청 실패: {e} (시도 {attempt}/3)")
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
        sheet = spreadsheet.worksheet(VIDEO_SHEET_NAME)
    except gspread.WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title=VIDEO_SHEET_NAME, rows="1000", cols=str(len(HEADERS)))
        sheet.freeze(rows=1)
        sheet.append_row(HEADERS)
        print(f"  시트 '{VIDEO_SHEET_NAME}' 새로 생성됨")

    return sheet


# ─────────────────────────────────────────
# 메인 동기화 로직
# ─────────────────────────────────────────

def run_sync(from_date: datetime, to_date: datetime):
    print(f"\n=== TikTok → Sheets 동기화 시작 ===")
    print(f"기간: {from_date.strftime('%Y-%m-%d')} ~ {to_date.strftime('%Y-%m-%d')}")

    sheet = get_sheet()

    # 기존 데이터 로드 (헤더 포함)
    for attempt in range(1, 6):
        try:
            existing = sheet.get_all_values()
            break
        except Exception as e:
            if attempt == 5:
                raise
            print(f"  시트 읽기 실패 (시도 {attempt}/5), 재시도 중...")
            time.sleep(3 * attempt)

    # Video ID → 행번호(1-based) 매핑
    video_index_map: dict[str, int] = {}
    if len(existing) <= 1:
        # 헤더만 있거나 비어있으면 헤더 보장
        if not existing:
            sheet.append_row(HEADERS)
    else:
        for i, row in enumerate(existing[1:], start=2):  # 2행부터 (1행=헤더)
            vid = str(row[0]).strip().lstrip("'")
            if vid:
                video_index_map[vid] = i

    updated_at = datetime.now(LA_TZ).strftime("%Y-%m-%d %H:%M:%S")
    page_token = None
    page_count = 0
    update_count = 0
    new_count = 0

    # 배치 업데이트용 버퍼
    batch_updates: list[dict] = []  # {"range": "A2:M2", "values": [[...]]}
    append_rows: list[list] = []

    while True:
        print(f"  페이지 {page_count + 1} 요청 중... (page_token={page_token})")
        result = fetch_video_performance(from_date, to_date, page_token)

        if not result:
            print("  API 오류 - 중단")
            break

        videos = result.get("data", {}).get("videos") or []

        for video in videos:
            video_id = str(video.get("id") or "").strip()
            if not video_id:
                continue

            post_time_str = video.get("video_post_time") or ""
            try:
                post_date = datetime.fromisoformat(post_time_str.replace("Z", "+00:00")) if post_time_str else datetime(1970, 1, 1, tzinfo=timezone.utc)
                if post_date.tzinfo is None:
                    post_date = post_date.replace(tzinfo=timezone.utc)
            except ValueError:
                post_date = datetime(1970, 1, 1, tzinfo=timezone.utc)

            # 기간 필터
            from_aware = from_date.replace(tzinfo=timezone.utc) if from_date.tzinfo is None else from_date
            to_aware = to_date.replace(tzinfo=timezone.utc) if to_date.tzinfo is None else to_date
            if not (from_aware <= post_date <= to_aware):
                continue

            gmv = video.get("gmv") or {}
            gmv_amount = float(gmv.get("amount") or 0)
            gmv_currency = gmv.get("currency") or ""
            sku_orders = video.get("sku_orders") or 0
            units_sold = video.get("units_sold") or 0
            views = video.get("views") or 0
            ctr = video.get("click_through_rate") or 0
            products = video.get("products") or []
            product_ids = ", ".join(str(p.get("id") or "") for p in products)
            product_names = ", ".join(str(p.get("name") or "") for p in products)

            row_data = [
                "'" + video_id, post_time_str, video.get("username") or "", video.get("title") or "",
                gmv_amount, gmv_currency, sku_orders, units_sold,
                views, ctr, product_ids, product_names, updated_at
            ]

            if video_id in video_index_map:
                if video_index_map[video_id] != "NEW":
                    target_row = video_index_map[video_id]
                    col_end = chr(ord("A") + len(HEADERS) - 1)
                    batch_updates.append({
                        "range": f"'{VIDEO_SHEET_NAME}'!A{target_row}:{col_end}{target_row}",
                        "values": [row_data]
                    })
                    update_count += 1
            else:
                append_rows.append(row_data)
                video_index_map[video_id] = "NEW"
                new_count += 1

        new_token = result.get("data", {}).get("next_page_token") or None
        if not new_token or new_token == page_token:
            break
        page_token = new_token
        page_count += 1
        time.sleep(0.3)

    # ─── 시트 쓰기 ───
    spreadsheet = sheet.spreadsheet

    if batch_updates:
        print(f"  기존 {update_count}건 업데이트 중...")
        # gspread batch_update
        body = {"valueInputOption": "USER_ENTERED", "data": batch_updates}
        spreadsheet.values_batch_update(body)

    if append_rows:
        print(f"  신규 {new_count}건 추가 중...")
        sheet.append_rows(append_rows, value_input_option="USER_ENTERED")

    print(f"\n✅ 완료! 업데이트 {update_count}건 / 신규 {new_count}건")


# ─────────────────────────────────────────
# 실행 진입점
# ─────────────────────────────────────────

def sync_last_30_days():
    """최근 30일 동기화 (Apps Script syncShopVideosToSheet 대응)"""
    now = datetime.now(timezone.utc)
    from_date = now - timedelta(days=30)
    run_sync(from_date, now)


def sync_by_date_range(start_str: str, end_str: str):
    """날짜 범위 동기화 (Apps Script syncVideosByDateRange 대응)"""
    from_date = datetime.strptime(start_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    to_date = datetime.strptime(end_str, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
    run_sync(from_date, to_date)


if __name__ == "__main__":
    # 최근 30일 실행
    sync_last_30_days()

    # 날짜 범위 지정 실행 예시:
    # sync_by_date_range("2024-04-01", "2024-04-30")
