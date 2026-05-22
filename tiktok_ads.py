"""TikTok Ads API (GMV MAX) → Google Sheets '광고성과' 탭"""
import json
import os
import time
import re

import requests
from google.oauth2.service_account import Credentials
import gspread

# ─────────────────────────────────────────
# 설정
# ─────────────────────────────────────────
ADVERTISER_ID        = "7573855166672355345"
STORE_ID             = "7494221571082258140"

SPREADSHEET_ID       = "1AhVPPUq6Npri72uhtFcOUVMBl1jA7nf2P0qDCDRRKfA"
SHEET_NAME           = "광고성과"
SERVICE_ACCOUNT_FILE = "service_account.json"
TOKEN_FILE           = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_tokens.json")

BASE = "https://business-api.tiktok.com/open_api/v1.3"

METRICS = [
    "creative_delivery_status",
    "cost",
    "orders",
    "cost_per_order",
    "gross_revenue",
    "roi",
    "product_impressions",
    "product_clicks",
    "product_click_rate",
    "ad_click_rate",
    "ad_conversion_rate",
    "ad_video_view_rate_2s",
    "ad_video_view_rate_6s",
    "ad_video_view_rate_p25",
    "ad_video_view_rate_p50",
    "ad_video_view_rate_p75",
    "ad_video_view_rate_p100",
]

HEADERS = [
    "날짜", "소재ID", "캠페인명", "아이템그룹명",
    "게재상태", "지출금액", "주문수", "주문당비용", "총매출(GMV)", "ROI",
    "상품노출수", "상품클릭수", "상품클릭률",
    "광고클릭률", "광고전환율",
    "2초시청률", "6초시청률", "25%시청률", "50%시청률", "75%시청률", "100%시청률",
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
# 날짜
# ─────────────────────────────────────────
def parse_date_range(raw: str):
    nums = re.findall(r"\d{4}[-./]\d{1,2}[-./]\d{1,2}", raw)
    if len(nums) < 2:
        raise ValueError("날짜 형식 오류. 예: 2026-05-01 ~ 2026-05-15")
    def norm(s): return re.sub(r"[./]", "-", s)
    return norm(nums[0]), norm(nums[1])


# ─────────────────────────────────────────
# 캠페인 목록 자동 조회
# ─────────────────────────────────────────
def get_campaign_ids(token: str) -> list[str]:
    headers = {"Access-Token": token}
    # GMV MAX 전용 엔드포인트 우선 시도, 없으면 일반 엔드포인트
    for path in ["/gmv_max/campaign/get/", "/campaign/get/"]:
        try:
            r = requests.get(f"{BASE}{path}", headers=headers, params={
                "advertiser_id": ADVERTISER_ID,
                "page_size": 100,
                "filtering": json.dumps({"primary_status": "STATUS_ALL"}),
            }, timeout=30)
            d = r.json()
            if d.get("code") == 0:
                ids = [c["campaign_id"] for c in d.get("data", {}).get("list", [])]
                if ids:
                    print(f"  캠페인 {len(ids)}개 발견: {ids}")
                    return ids
        except Exception as e:
            print(f"  캠페인 조회 오류: {e}")
    return []


# ─────────────────────────────────────────
# 아이템그룹(adgroup) 목록 자동 조회
# ─────────────────────────────────────────
def get_item_group_ids(token: str, campaign_ids: list[str]) -> dict:
    """campaign_id → (campaign_name, [(adgroup_id, adgroup_name)]) 매핑 반환"""
    headers = {"Access-Token": token}
    result = {}
    for path in ["/gmv_max/adgroup/get/", "/adgroup/get/"]:
        try:
            r = requests.get(f"{BASE}{path}", headers=headers, params={
                "advertiser_id": ADVERTISER_ID,
                "page_size": 100,
                "filtering": json.dumps({
                    "campaign_ids": campaign_ids,
                    "primary_status": "STATUS_ALL",
                }),
            }, timeout=30)
            d = r.json()
            if d.get("code") == 0:
                for g in d.get("data", {}).get("list", []):
                    cid = str(g.get("campaign_id", ""))
                    gid = str(g.get("adgroup_id") or g.get("item_group_id", ""))
                    gname = g.get("adgroup_name") or g.get("item_group_name", "")
                    cname = g.get("campaign_name", "")
                    if cid not in result:
                        result[cid] = (cname, [])
                    result[cid][1].append((gid, gname))
                if result:
                    total_groups = sum(len(v[1]) for v in result.values())
                    print(f"  아이템그룹 {total_groups}개 발견")
                    return result
        except Exception as e:
            print(f"  아이템그룹 조회 오류 ({path}): {e}")
    return {}


# ─────────────────────────────────────────
# 리포트 조회 (campaign + item_group 조합별)
# ─────────────────────────────────────────
def fetch_report(token: str, start_date: str, end_date: str,
                 campaign_id: str, group_ids: list[str],
                 campaign_name: str, group_name_map: dict) -> list[list]:
    headers = {"Access-Token": token}
    all_rows = []
    page = 1
    while True:
        params = {
            "advertiser_id": ADVERTISER_ID,
            "store_ids": json.dumps([STORE_ID]),
            "dimensions": json.dumps(["stat_time_day", "item_id"]),
            "metrics": json.dumps(METRICS),
            "start_date": start_date,
            "end_date": end_date,
            "filtering": json.dumps({
                "campaign_ids": [campaign_id],
                "item_group_ids": group_ids,
            }),
            "page": page,
            "page_size": 1000,
        }
        for attempt in range(1, 4):
            try:
                r = requests.get(f"{BASE}/gmv_max/report/get/", headers=headers,
                                 params=params, timeout=30)
                d = r.json()
                if d.get("code") == 0:
                    for item in d.get("data", {}).get("list", []):
                        dims = item.get("dimensions", {})
                        mets = item.get("metrics", {})
                        gid = dims.get("item_group_id", "")
                        all_rows.append([
                            dims.get("stat_time_day", "")[:10],
                            dims.get("item_id", ""),
                            campaign_name,
                            group_name_map.get(gid, ""),
                            mets.get("creative_delivery_status", ""),
                            mets.get("cost", ""),
                            mets.get("orders", ""),
                            mets.get("cost_per_order", ""),
                            mets.get("gross_revenue", ""),
                            mets.get("roi", ""),
                            mets.get("product_impressions", ""),
                            mets.get("product_clicks", ""),
                            mets.get("product_click_rate", ""),
                            mets.get("ad_click_rate", ""),
                            mets.get("ad_conversion_rate", ""),
                            mets.get("ad_video_view_rate_2s", ""),
                            mets.get("ad_video_view_rate_6s", ""),
                            mets.get("ad_video_view_rate_p25", ""),
                            mets.get("ad_video_view_rate_p50", ""),
                            mets.get("ad_video_view_rate_p75", ""),
                            mets.get("ad_video_view_rate_p100", ""),
                        ])
                    page_info = d.get("data", {}).get("page_info", {})
                    if page >= page_info.get("total_page", 1):
                        return all_rows
                    page += 1
                    time.sleep(0.3)
                    break
                else:
                    print(f"  [경고] code={d.get('code')}, msg={d.get('message')} (시도 {attempt}/3)")
                    if d.get("code") == 40002:
                        return all_rows
            except Exception as e:
                print(f"  [오류] {e} (시도 {attempt}/3)")
            time.sleep(2 * attempt)
        else:
            break
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
        sheet = spreadsheet.add_worksheet(title=SHEET_NAME, rows="5000", cols=str(len(HEADERS)))
        sheet.append_row(HEADERS)
        sheet.freeze(rows=1)
        print(f"  시트 '{SHEET_NAME}' 새로 생성됨")
    return sheet


def save(rows: list[list]):
    if not rows:
        print("  저장할 데이터 없음")
        return
    sheet = get_sheet()
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


# ─────────────────────────────────────────
# 메인
# ─────────────────────────────────────────
def main():
    raw = input("기간 입력 (예: 2026-05-01 ~ 2026-05-15): ").strip()
    start_date, end_date = parse_date_range(raw)
    print(f"\n=== TikTok GMV MAX 광고 성과 [{start_date} ~ {end_date}] ===")

    token = get_token()

    print("  캠페인 목록 조회 중...")
    campaign_ids = get_campaign_ids(token)
    if not campaign_ids:
        print("  ❌ GMV MAX 캠페인을 찾을 수 없습니다.")
        return

    print("  아이템그룹 목록 조회 중...")
    campaign_map = get_item_group_ids(token, campaign_ids)
    if not campaign_map:
        print("  ❌ 아이템그룹을 찾을 수 없습니다.")
        return

    all_rows = []
    for cid, (cname, groups) in campaign_map.items():
        group_ids = [g[0] for g in groups]
        group_name_map = {g[0]: g[1] for g in groups}
        print(f"  [{cname}] 소재 데이터 조회 중...")
        rows = fetch_report(token, start_date, end_date, cid, group_ids, cname, group_name_map)
        all_rows.extend(rows)

    print(f"  총 {len(all_rows)}행 수집")
    save(all_rows)


if __name__ == "__main__":
    main()
