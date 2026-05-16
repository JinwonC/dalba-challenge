"""
공통 유틸리티 모듈 - 모든 Analytics 스크립트에서 import해서 사용
"""
import hashlib
import hmac
import os
import sys
import time
from datetime import datetime, timedelta
from urllib.parse import urlencode, quote

import requests
from google.oauth2.service_account import Credentials
import gspread

# ─────────────────────────────────────────
# 설정값
# ─────────────────────────────────────────
APP_KEY = "6jd7l2nu36rd4"
APP_SECRET = "9ab6f9c3467d53c72ca6e346c18b8071338f0ce4"
ACCESS_TOKEN = "TTP_8qmwDAAAAAAKxe5s-tyxQjFx-BLmHCzEUHx_N8KtbJs8REguA-PlojAyV0wGbdEfcH65GTeVkz7R1pOu5g44xImqf4SrMwS1YxCDFaFiR71wCyyvCuiX9V4xVHdkwwVZjC2fEb9DckyVqVjeUiW-H2PBtsmHPpwLM6krtq-pI3-bR3oq5XS_LA"
REFRESH_TOKEN = "TTP_77fQXQAAAACRYHgjQ_4vEa-Xhe5ikMt0yvs0Zs2i5flXWHMzwGflyAsL_dJ53tHERRwYkVRh9AI"
SHOP_CIPHER = "TTP_uE19hAAAAADx5Flb4Y_fjmWFiQfOEyTT"

SPREADSHEET_ID = "1WdGbSdBik2MKtXBMEBQB52YB2hXxwABBA01nFpQUxnc"
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "service_account.json")
TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tokens.json")

BASE_URL = "https://open-api.tiktokglobalshop.com"


# ─────────────────────────────────────────
# 서명
# ─────────────────────────────────────────

def make_sign(path: str, params: dict) -> str:
    sorted_keys = sorted(params.keys())
    sign_str = APP_SECRET + path
    for key in sorted_keys:
        sign_str += key + str(params[key])
    sign_str += APP_SECRET
    return hmac.new(APP_SECRET.encode(), sign_str.encode(), hashlib.sha256).hexdigest()


# ─────────────────────────────────────────
# 토큰 관리
# ─────────────────────────────────────────

def get_current_token() -> str:
    import json
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            data = json.load(f)
            if data.get("access_token"):
                return data["access_token"]
    return ACCESS_TOKEN


def refresh_token_if_needed() -> str:
    params = {
        "app_key": APP_KEY,
        "app_secret": APP_SECRET,
        "refresh_token": REFRESH_TOKEN,
        "grant_type": "refresh_token",
    }
    resp = requests.get("https://auth.tiktok-shops.com/api/v2/token/refresh", params=params, timeout=30)
    data = resp.json()
    if data.get("code") == 0:
        import json
        new_token = data["data"]["access_token"]
        with open(TOKEN_FILE, "w") as f:
            json.dump({"access_token": new_token, "refresh_token": data["data"].get("refresh_token", REFRESH_TOKEN)}, f)
        print("  ✅ 토큰 자동 갱신 완료")
        return new_token
    return get_current_token()


# ─────────────────────────────────────────
# API 호출
# ─────────────────────────────────────────

def call_api(path: str, extra_params: dict) -> dict | None:
    for attempt in range(1, 4):
        timestamp = str(int(time.time()))
        params = {
            "app_key": APP_KEY,
            "shop_cipher": SHOP_CIPHER,
            "timestamp": timestamp,
            **extra_params
        }
        params["sign"] = make_sign(path, params)
        url = BASE_URL + path + "?" + urlencode(params, quote_via=quote)
        headers = {
            "x-tts-access-token": get_current_token(),
            "content-type": "application/json"
        }
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            data = resp.json()
            if data.get("code") == 0:
                return data
            if data.get("code") == 105002:
                print("  [토큰 만료] 자동 갱신 중...")
                refresh_token_if_needed()
                continue
            print(f"  [경고] code={data.get('code')}, msg={data.get('message')} (시도 {attempt}/3)")
        except Exception as e:
            print(f"  [오류] {e} (시도 {attempt}/3)")
        time.sleep(2 * attempt)
    return None


# ─────────────────────────────────────────
# Google Sheets
# ─────────────────────────────────────────

def get_sheet(sheet_name: str):
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    try:
        sheet = spreadsheet.worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title=sheet_name, rows="1000", cols="30")
        print(f"  시트 '{sheet_name}' 새로 생성됨")
    return sheet


def write_to_sheet(sheet, headers: list, rows: list):
    if not rows:
        print("  저장할 데이터가 없습니다.")
        return

    # 헤더가 없으면 추가
    existing = sheet.row_values(1)
    if not existing:
        sheet.append_row(headers)
        sheet.freeze(rows=1)

    for attempt in range(1, 6):
        try:
            sheet.append_rows(rows, value_input_option="USER_ENTERED")
            print(f"  ✅ {len(rows)}행 저장 완료")
            return
        except Exception as e:
            if attempt == 5:
                raise
            print(f"  시트 쓰기 실패 (시도 {attempt}/5)...")
            time.sleep(3 * attempt)


# ─────────────────────────────────────────
# 날짜 입력
# ─────────────────────────────────────────

def get_date_input() -> str:
    if len(sys.argv) > 1:
        return sys.argv[1]
    return input("날짜 입력 (예: 2026-05-15): ").strip()
