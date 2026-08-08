"""TikTok Shop Performance 일 단위(granularity=1D)
→ US매출/지표 시트 'Get Shop Performance' 탭

/analytics/202509/shop/performance 를 30일 청크(실패 시 7일)로 조회,
intervals(일별)를 동적 평탄화해 날짜 오름차순으로 적재한다.
"""
import hashlib
import hmac
import json
import re
import sys
import time
from datetime import datetime, timedelta
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
SHEET_NAME = "Get Shop Performance"
SERVICE_ACCOUNT_FILE = "service_account.json"

BASE = "https://open-api.tiktokglobalshop.com"
PATH = "/analytics/202509/shop/performance"


def make_sign(path: str, params: dict) -> str:
    s = VIDEO_APP_SECRET + path
    for k in sorted(params.keys()):
        s += k + str(params[k])
    s += VIDEO_APP_SECRET
    return hmac.new(VIDEO_APP_SECRET.encode(), s.encode(), hashlib.sha256).hexdigest()


def api_get(extra: dict):
    params = {
        "app_key": VIDEO_APP_KEY,
        "shop_cipher": VIDEO_SHOP_CIPHER,
        "currency": "USD",
        "timestamp": str(int(time.time())),
        **extra,
    }
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
            if d.get("code") in (28001022, 36009004):
                return {"__range_error__": True, "message": d.get("message")}
            print(f"    [경고] code={d.get('code')}, msg={str(d.get('message'))[:80]} (시도 {attempt}/3)")
        except Exception as e:
            print(f"    [오류] {e} (시도 {attempt}/3)")
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


def main():
    raw = sys.argv[1] if len(sys.argv) > 1 else "2026-01-01 ~ 2026-08-07"
    nums = re.findall(r"\d{4}-\d{1,2}-\d{1,2}", raw)
    start = nums[0]
    end = nums[1] if len(nums) > 1 else nums[0]
    print(f"\n=== Shop Performance (1D) [{start} ~ {end}] ===")

    s_dt = datetime.strptime(start, "%Y-%m-%d")
    e_dt = datetime.strptime(end, "%Y-%m-%d")
    chunk_days = 30
    by_date: dict[str, dict] = {}
    all_keys: list[str] = []

    cur = s_dt
    while cur <= e_dt:
        c_end = min(cur + timedelta(days=chunk_days - 1), e_dt)
        cs = cur.strftime("%Y-%m-%d")
        ce = (c_end + timedelta(days=1)).strftime("%Y-%m-%d")  # end_date_lt = 배타적
        print(f"  청크 조회: {cs} ~ {c_end.strftime('%Y-%m-%d')}")
        d = api_get({"start_date_ge": cs, "end_date_lt": ce, "granularity": "1D"})
        if d and d.get("__range_error__") and chunk_days > 7:
            print(f"    → 오류({str(d.get('message'))[:60]}), 청크 7일로 축소")
            chunk_days = 7
            continue
        cur = c_end + timedelta(days=1)
        if not d or d.get("__range_error__"):
            continue
        perf = d.get("data", {}).get("performance") or {}
        for iv in perf.get("intervals") or []:
            f = flatten(iv)
            key = str(f.get("start_date") or f.get("date") or "")
            for k in f:
                if k not in all_keys:
                    all_keys.append(k)
            by_date[key] = f
        time.sleep(0.2)

    rows_src = sorted(by_date.values(),
                      key=lambda r: str(r.get("start_date") or r.get("date") or ""))
    print(f"  총 {len(rows_src)}일치 수집, 필드 {len(all_keys)}개")
    print(f"  필드 목록: {all_keys}")
    if not rows_src:
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
    sheet.resize(rows=len(rows_src) + 10, cols=max(len(all_keys), 10))

    data = [all_keys] + [[r.get(k, "") for k in all_keys] for r in rows_src]
    for attempt in range(1, 9):
        try:
            sheet.update(data, value_input_option="USER_ENTERED")
            sheet.freeze(rows=1)
            print(f"  ✅ '{SHEET_NAME}' 탭에 {len(rows_src)}행 저장 완료")
            return
        except Exception as e:
            if attempt == 8:
                raise
            wait = min(3 * attempt, 30)
            print(f"  시트 쓰기 실패 (시도 {attempt}/8), {wait}초 후 재시도... ({e})")
            time.sleep(wait)


if __name__ == "__main__":
    main()
