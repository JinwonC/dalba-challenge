"""TikTok Shop LIVE Performance (202509) → '라이브성과' 탭

/analytics/202509/shop_lives/performance 를 청크(30일→실패시 7일) 조회해
응답 필드를 평탄화, 시작시간 오름차순(과거→최신)으로
스프레드시트 15dP91bH...(US 매출/지표)의 '라이브성과' 탭에 덤프한다.
sales_performance / interaction_performance 중첩 필드 포함.
"""
import hashlib
import hmac
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, quote

import requests
from google.oauth2.service_account import Credentials
import gspread
from token_manager import get_valid_token, handle_token_expired

VIDEO_APP_KEY = "6jd7l2nu36rd4"
VIDEO_APP_SECRET = "9ab6f9c3467d53c72ca6e346c18b8071338f0ce4"
VIDEO_ACCESS_TOKEN = "TTP_8qmwDAAAAAAKxe5s-tyxQjFx-BLmHCzEUHx_N8KtbJs8REguA-PlojAyV0wGbdEfcH65GTeVkz7R1pOu5g44xImqf4SrMwS1YxCDFaFiR71wCyyvCuiX9V4xVHdkwwVZjC2fEb9DckyVqVjeUiW-H2PBtsmHPpwLM6krtq-pI3-bR3oq5XS_LA"
VIDEO_REFRESH_TOKEN = "TTP_77fQXQAAAACRYHgjQ_4vEa-Xhe5ikMt0yvs0Zs2i5flXWHMzwGflyAsL_dJ53tHERRwYkVRh9AI"
VIDEO_SHOP_CIPHER = "TTP_uE19hAAAAADx5Flb4Y_fjmWFiQfOEyTT"

SPREADSHEET_ID = "15dP91bH_skc7ZzcJ3ehH9H4IKCzSxcfuOcREr3OaL0o"  # US 매출/지표
SHEET_NAME = "라이브성과"
SERVICE_ACCOUNT_FILE = "service_account.json"

PATH = "/analytics/202509/shop_lives/performance"
BASE = "https://open-api.tiktokglobalshop.com"

LA_TZ = timezone(timedelta(hours=-8))


def make_sign(path: str, params: dict) -> str:
    s = VIDEO_APP_SECRET + path
    for k in sorted(params.keys()):
        s += k + str(params[k])
    s += VIDEO_APP_SECRET
    return hmac.new(VIDEO_APP_SECRET.encode(), s.encode(), hashlib.sha256).hexdigest()


def fetch_page(start: str, end: str, page_token: str | None):
    params = {
        "app_key": VIDEO_APP_KEY,
        "shop_cipher": VIDEO_SHOP_CIPHER,
        "start_date_ge": start,
        "end_date_lt": end,
        "page_size": "100",
        "account_type": "ALL",
        "currency": "USD",
        "sort_field": "gmv",
        "sort_order": "DESC",
        "timestamp": str(int(time.time())),
    }
    if page_token:
        params["page_token"] = page_token
    params["sign"] = make_sign(PATH, params)
    url = BASE + PATH + "?" + urlencode(params, quote_via=quote)
    headers = {"content-type": "application/json",
               "x-tts-access-token": get_valid_token(VIDEO_ACCESS_TOKEN, VIDEO_REFRESH_TOKEN)}
    for attempt in range(1, 4):
        try:
            d = requests.get(url, headers=headers, timeout=30).json()
            if d.get("code") == 0:
                return d
            if d.get("code") == 105002:
                new_token = handle_token_expired(VIDEO_REFRESH_TOKEN)
                if new_token:
                    headers["x-tts-access-token"] = new_token
                    continue
            print(f"  [경고] code={d.get('code')}, msg={d.get('message')} (시도 {attempt}/3)")
        except Exception as e:
            print(f"  [오류] {e} (시도 {attempt}/3)")
        time.sleep(2 * attempt)
    return None


def flatten(obj, prefix="") -> dict:
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                out.update(flatten(v, key))
            elif isinstance(v, list):
                out[key] = json.dumps(v, ensure_ascii=False)[:1000]
            else:
                out[key] = v
    return out


def fetch_range(start: str, end: str) -> list[dict] | None:
    out = []
    token = None
    page = 0
    while True:
        page += 1
        d = fetch_page(start, end, token)
        if not d:
            return None if page == 1 else out
        out.extend(d.get("data", {}).get("live_stream_sessions") or [])
        nt = d.get("data", {}).get("next_page_token") or None
        if not nt or nt == token:
            return out
        token = nt
        time.sleep(0.3)


def ts_to_la(ts) -> str:
    try:
        return datetime.fromtimestamp(int(ts), LA_TZ).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return ""


def main():
    raw = sys.argv[1] if len(sys.argv) > 1 else "2026-01-01 ~ 2026-08-07"
    nums = re.findall(r"\d{4}-\d{1,2}-\d{1,2}", raw)
    start = nums[0]
    end = nums[1] if len(nums) > 1 else nums[0]
    print(f"\n=== Shop LIVE Performance 202509 [{start} ~ {end}] ===")

    merged: dict[str, dict] = {}
    all_keys: list[str] = []
    s_dt = datetime.strptime(start, "%Y-%m-%d")
    e_dt = datetime.strptime(end, "%Y-%m-%d")
    chunk_days = 30
    cur = s_dt
    while cur <= e_dt:
        c_end = min(cur + timedelta(days=chunk_days - 1), e_dt)
        cs, ce = cur.strftime("%Y-%m-%d"), c_end.strftime("%Y-%m-%d")
        print(f"  청크 조회: {cs} ~ {ce}")
        sessions = fetch_range(cs, ce)
        if sessions is None and chunk_days > 7:
            print("    → 실패, 청크를 7일로 축소해 재시도")
            chunk_days = 7
            continue
        for s in (sessions or []):
            f = flatten(s)
            # 시작/종료 unix timestamp → LA 시간 컬럼 추가
            f["시작일시(LA)"] = ts_to_la(f.get("start_time"))
            f["종료일시(LA)"] = ts_to_la(f.get("end_time"))
            sid = str(f.get("id", ""))
            merged[sid] = f  # 라이브 세션은 이산 이벤트 → id 기준 최신값 유지
            for k in f:
                if k not in all_keys:
                    all_keys.append(k)
        cur = c_end + timedelta(days=1)

    sessions_flat = [v for v in merged.values() if v.get("시작일시(LA)", "")[:10] >= start]
    sessions_flat.sort(key=lambda v: str(v.get("시작일시(LA)", "")))

    print(f"  총 {len(sessions_flat)}개 라이브 세션, 필드 {len(all_keys)}개")
    print(f"  필드 목록: {all_keys}")

    if not sessions_flat:
        print("  데이터 없음 - 종료")
        return

    creds = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"])
    ss = gspread.authorize(creds).open_by_key(SPREADSHEET_ID)
    try:
        sheet = ss.worksheet(SHEET_NAME)
        sheet.clear()
    except gspread.WorksheetNotFound:
        sheet = ss.add_worksheet(title=SHEET_NAME, rows="1000", cols=str(max(len(all_keys), 10)))
    sheet.resize(rows=len(sessions_flat) + 10, cols=max(len(all_keys), 10))

    rows = [all_keys]
    for f in sessions_flat:
        rows.append([f.get(k, "") for k in all_keys])

    for attempt in range(1, 9):
        try:
            sheet.update(rows, value_input_option="USER_ENTERED")
            sheet.freeze(rows=1)
            print(f"  ✅ '{SHEET_NAME}' 탭에 {len(rows)-1}행 저장 완료")
            return
        except Exception as e:
            if attempt == 8:
                raise
            wait = min(3 * attempt, 30)
            print(f"  시트 쓰기 실패 (시도 {attempt}/8), {wait}초 후 재시도... ({e})")
            time.sleep(wait)


if __name__ == "__main__":
    main()
