"""TikTok Shop Get Product SKPP Detail
→ 스프레드시트 1fVWfi... 'Get Product SKPP Detail' 탭

SKPP는 상품별 '현재 진단 스냅샷'이라 기간 개념이 없다(update_time만 존재).
1) 상품 목록 검색으로 product_id 수집 (경로/메서드 자동 탐색)
2) 상품별 SKPP 상세 조회 → 태스크 단위 행으로 저장
   (태스크가 없으면 상품 요약 1행)
"""
import hashlib
import hmac
import json
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urlencode, quote

import requests
from google.oauth2.service_account import Credentials
import gspread
from token_manager import get_valid_token, handle_token_expired

APP_KEY = "6jd7l2nu36rd4"
APP_SECRET = "9ab6f9c3467d53c72ca6e346c18b8071338f0ce4"
ACCESS_TOKEN = "TTP_8qmwDAAAAAAKxe5s-tyxQjFx-BLmHCzEUHx_N8KtbJs8REguA-PlojAyV0wGbdEfcH65GTeVkz7R1pOu5g44xImqf4SrMwS1YxCDFaFiR71wCyyvCuiX9V4xVHdkwwVZjC2fEb9DckyVqVjeUiW-H2PBtsmHPpwLM6krtq-pI3-bR3oq5XS_LA"
REFRESH_TOKEN = "TTP_77fQXQAAAACRYHgjQ_4vEa-Xhe5ikMt0yvs0Zs2i5flXWHMzwGflyAsL_dJ53tHERRwYkVRh9AI"
SHOP_CIPHER = "TTP_uE19hAAAAADx5Flb4Y_fjmWFiQfOEyTT"

SPREADSHEET_ID = "1fVWfictZo6BiKyWO-eFfSo3fAVscOQMPVg1gqa5oMWI"
SHEET_NAME = "Get Product SKPP Detail"
SERVICE_ACCOUNT_FILE = "service_account.json"

BASE = "https://open-api.tiktokglobalshop.com"
LA_TZ = ZoneInfo("America/Los_Angeles")

PRODUCT_SEARCH_PATHS = [
    "/product/202312/products/search",
    "/product/202309/products/search",
    "/product/202502/products/search",
]
SKPP_TEMPLATES = [
    "/product/202409/products/{pid}/skpp_detail",
    "/product/202502/products/{pid}/skpp_detail",
    "/product/202312/products/{pid}/skpp_detail",
    "/product/202409/products/{pid}/skpp",
    "/product/202506/products/{pid}/skpp_detail",
]

HEADERS_ROW = [
    "상품ID", "SKPP상태", "제휴프로그램상태", "총점", "목표점수", "업데이트(LA)",
    "태스크_카테고리", "태스크명", "현재값", "목표값", "통과여부", "개선제안(JSON)",
    "리워드(JSON)",
]


def sign_str(path: str, params: dict, body: str = "") -> str:
    s = APP_SECRET + path
    for k in sorted(params.keys()):
        s += k + str(params[k])
    s += body
    return hmac.new(APP_SECRET.encode(), (s + APP_SECRET).encode(), hashlib.sha256).hexdigest()


def call(path: str, method: str = "GET", body_obj: dict | None = None, extra: dict | None = None):
    params = {"app_key": APP_KEY, "shop_cipher": SHOP_CIPHER,
              "timestamp": str(int(time.time())), **(extra or {})}
    body = json.dumps(body_obj, separators=(",", ":")) if body_obj is not None else ""
    params["sign"] = sign_str(path, dict(params), body)
    headers = {"content-type": "application/json",
               "x-tts-access-token": get_valid_token(ACCESS_TOKEN, REFRESH_TOKEN)}
    for attempt in range(1, 4):
        try:
            if method == "POST":
                r = requests.post(BASE + path, params=params, headers=headers, data=body, timeout=45)
            else:
                r = requests.get(BASE + path + "?" + urlencode(params, quote_via=quote),
                                 headers=headers, timeout=45)
            d = r.json()
            if d.get("code") == 105002:
                nt = handle_token_expired(REFRESH_TOKEN)
                if nt:
                    headers["x-tts-access-token"] = nt
                    continue
            return d
        except Exception as e:
            print(f"    [오류] {e} (시도 {attempt}/3)")
            time.sleep(1.5 * attempt)
    return None


def collect_products() -> list[str]:
    for path in PRODUCT_SEARCH_PATHS:
        ids: list[str] = []
        page_token = None
        ok = False
        while True:
            extra = {"page_size": "100"}
            if page_token:
                extra["page_token"] = page_token
            d = call(path, "POST", {"status": "ACTIVATE"}, extra)
            code = d.get("code") if d else None
            if code != 0:
                if not ok:
                    print(f"  probe POST {path} → code={code} msg={str(d.get('message'))[:60] if d else '-'}")
                break
            ok = True
            data = d.get("data", {})
            for p in data.get("products") or []:
                pid = str(p.get("id", ""))
                if pid:
                    ids.append(pid)
            nt = data.get("next_page_token") or None
            if not nt or nt == page_token:
                break
            page_token = nt
            time.sleep(0.2)
        if ok and ids:
            print(f"  ✅ 상품 목록 경로: {path} — {len(ids)}개")
            return ids
    return []


def product_ids_from_sku_sheet() -> list[str]:
    """상품 목록 API 권한이 없을 때: US매출/지표 시트의 SKU Order 탭에서 상품ID 확보."""
    creds = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"])
    ss = gspread.authorize(creds).open_by_key("15dP91bH_skc7ZzcJ3ehH9H4IKCzSxcfuOcREr3OaL0o")
    vals = ss.worksheet("(중요, 자동) SKU Order").col_values(2)[1:]
    ids: list[str] = []
    for v in vals:
        v = str(v).strip().lstrip("'")
        if v and v not in ids:
            ids.append(v)
    return ids


def probe_skpp(pid: str):
    for tpl in SKPP_TEMPLATES:
        d = call(tpl.format(pid=pid), "GET")
        code = d.get("code") if d else None
        print(f"  probe {tpl} → code={code} msg={str(d.get('message'))[:60] if d else '-'}")
        if code == 0:
            return tpl
        time.sleep(0.2)
    return None


def la(ts) -> str:
    try:
        v = int(ts)
        if v > 10_000_000_000:
            v //= 1000
        return datetime.fromtimestamp(v, LA_TZ).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return ""


def rows_of(d: dict) -> list[list]:
    base = [
        d.get("product_id", ""), d.get("skpp_status", ""),
        d.get("affiliate_program_status", ""),
        d.get("total_score", ""), d.get("target_score", ""), la(d.get("update_time")),
    ]
    rewards = json.dumps(d.get("rewards") or [], ensure_ascii=False)[:3000]
    tasks = d.get("task_details") or []
    if not tasks:
        return [base + ["", "", "", "", "", ""] + [rewards]]
    out = []
    for t in tasks:
        out.append(base + [
            t.get("category", ""), t.get("name", ""),
            t.get("current_value", ""), t.get("target_value", ""), t.get("passed", ""),
            json.dumps(t.get("action_suggestions") or [], ensure_ascii=False)[:1000],
        ] + [rewards])
    return out


def main():
    print("\n=== Get Product SKPP Detail (현재 스냅샷) ===")
    print("  [1/3] 상품 목록 수집...")
    pids = collect_products()
    if not pids:
        print("  상품 목록 API 사용 불가 → SKU Order 탭에서 상품ID 확보 시도")
        pids = product_ids_from_sku_sheet()
        print(f"    시트에서 상품 {len(pids)}개 확보")
    if not pids:
        print("  ❌ 상품ID를 확보하지 못함")
        sys.exit(1)

    print("  [2/3] SKPP 엔드포인트 탐색...")
    tpl = probe_skpp(pids[0])
    if not tpl:
        print("  ❌ SKPP 엔드포인트 확인 실패 — 문서 경로 필요")
        sys.exit(1)
    print(f"    ✅ {tpl}")

    print("  [3/3] 상품별 SKPP 조회...")
    rows: list[list] = []
    for i, pid in enumerate(pids, 1):
        d = call(tpl.format(pid=pid), "GET")
        if d and d.get("code") == 0:
            rows.extend(rows_of(d.get("data") or {}))
        if i % 50 == 0:
            print(f"    진행 {i}/{len(pids)} · 누적 {len(rows)}행")
        time.sleep(0.12)

    print(f"  총 {len(rows)}행 수집")
    if not rows:
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
        sheet = ss.add_worksheet(title=SHEET_NAME, rows="1000", cols=str(len(HEADERS_ROW)))
    sheet.resize(rows=len(rows) + 10, cols=len(HEADERS_ROW))

    data_rows = [HEADERS_ROW] + rows
    for attempt in range(1, 9):
        try:
            sheet.update(data_rows, value_input_option="USER_ENTERED")
            sheet.freeze(rows=1)
            print(f"  ✅ '{SHEET_NAME}' 탭에 {len(rows)}행 저장 완료")
            return
        except Exception as e:
            if attempt == 8:
                raise
            wait = min(3 * attempt, 30)
            print(f"  시트 쓰기 실패 (시도 {attempt}/8), {wait}초 후 재시도... ({e})")
            time.sleep(wait)


if __name__ == "__main__":
    main()
