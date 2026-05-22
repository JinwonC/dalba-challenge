"""TikTok Ads API (GMV MAX) 소재별 성과 → Google Sheets '광고소재성과' 탭"""
import json, os, time, re
import requests
from google.oauth2.service_account import Credentials
import gspread

ADVERTISER_ID        = "7573855166672355345"
STORE_ID             = "7494221571082258140"
SPREADSHEET_ID       = "1AhVPPUq6Npri72uhtFcOUVMBl1jA7nf2P0qDCDRRKfA"
SHEET_NAME           = "광고소재성과"
SERVICE_ACCOUNT_FILE = "service_account.json"
TOKEN_FILE           = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_tokens.json")
BASE                 = "https://business-api.tiktok.com/open_api/v1.3"
GMV_REPORT_URL       = f"{BASE}/gmv_max/report/get/"

METRICS = [
    "creative_delivery_status",
    "cost", "orders", "cost_per_order", "gross_revenue", "roi",
    "product_impressions", "product_clicks", "product_click_rate",
    "ad_click_rate", "ad_conversion_rate",
    "ad_video_view_rate_2s", "ad_video_view_rate_6s",
    "ad_video_view_rate_p25", "ad_video_view_rate_p50",
    "ad_video_view_rate_p75", "ad_video_view_rate_p100",
]
HEADERS = [
    "날짜", "소재ID", "캠페인ID", "캠페인명", "아이템그룹ID",
    "게재상태", "지출금액", "주문수", "주문당비용", "총매출(GMV)", "ROI",
    "상품노출수", "상품클릭수", "상품클릭률",
    "광고클릭률", "광고전환율",
    "2초시청률", "6초시청률", "25%시청률", "50%시청률", "75%시청률", "100%시청률",
]


def get_token():
    with open(TOKEN_FILE) as f:
        return json.load(f).get("access_token", "")


def parse_date_range(raw):
    nums = re.findall(r"\d{4}[-./]\d{1,2}[-./]\d{1,2}", raw)
    if len(nums) < 2:
        raise ValueError("날짜 형식 오류. 예: 2026-05-01 ~ 2026-05-15")
    def norm(s): return re.sub(r"[./]", "-", s)
    return norm(nums[0]), norm(nums[1])


def api_get(token, params):
    for attempt in range(1, 4):
        try:
            r = requests.get(GMV_REPORT_URL, headers={"Access-Token": token},
                             params=params, timeout=30)
            d = r.json()
            if d.get("code") == 0:
                return d
            print(f"  [경고] code={d.get('code')}, msg={d.get('message')} (시도 {attempt}/3)")
            if d.get("code") == 40002:
                return None
        except Exception as e:
            print(f"  [오류] {e} (시도 {attempt}/3)")
        time.sleep(2 * attempt)
    return None


def get_campaign_ids(token, start_date, end_date):
    ids, page = set(), 1
    while True:
        d = api_get(token, {
            "advertiser_id": ADVERTISER_ID,
            "store_ids": json.dumps([STORE_ID]),
            "dimensions": json.dumps(["stat_time_day", "campaign_id"]),
            "metrics": json.dumps(["cost"]),
            "start_date": start_date, "end_date": end_date,
            "page": page, "page_size": 1000,
        })
        if not d:
            break
        for item in d.get("data", {}).get("list", []):
            ids.add(item["dimensions"]["campaign_id"])
        if page >= d.get("data", {}).get("page_info", {}).get("total_page", 1):
            break
        page += 1
        time.sleep(0.3)
    return list(ids)


def get_campaign_info(token, campaign_id):
    try:
        r = requests.get(f"{BASE}/campaign/gmv_max/info/",
                         headers={"Access-Token": token},
                         params={"advertiser_id": ADVERTISER_ID, "campaign_id": campaign_id},
                         timeout=30)
        d = r.json()
        if d.get("code") == 0:
            return d.get("data", {})
    except Exception as e:
        print(f"  [오류] campaign info {campaign_id}: {e}")
    return {}


def fetch_item_rows(token, start_date, end_date, campaign_id, item_group_ids, campaign_name):
    rows, page = [], 1
    while True:
        d = api_get(token, {
            "advertiser_id": ADVERTISER_ID,
            "store_ids": json.dumps([STORE_ID]),
            "dimensions": json.dumps(["stat_time_day", "item_id"]),
            "metrics": json.dumps(METRICS),
            "start_date": start_date, "end_date": end_date,
            "filtering": json.dumps({
                "campaign_ids": [campaign_id],
                "item_group_ids": item_group_ids,
            }),
            "page": page, "page_size": 1000,
        })
        if not d:
            break
        for item in d.get("data", {}).get("list", []):
            dims, mets = item["dimensions"], item["metrics"]
            item_id = dims.get("item_id", "")
            rows.append([
                dims.get("stat_time_day", "")[:10],
                "프로덕트카드" if item_id == "-1" else item_id,
                campaign_id, campaign_name,
                dims.get("item_group_id", ""),
                mets.get("creative_delivery_status", ""),
                mets.get("cost", ""), mets.get("orders", ""),
                mets.get("cost_per_order", ""), mets.get("gross_revenue", ""),
                mets.get("roi", ""),
                mets.get("product_impressions", ""), mets.get("product_clicks", ""),
                mets.get("product_click_rate", ""),
                mets.get("ad_click_rate", ""), mets.get("ad_conversion_rate", ""),
                mets.get("ad_video_view_rate_2s", ""), mets.get("ad_video_view_rate_6s", ""),
                mets.get("ad_video_view_rate_p25", ""), mets.get("ad_video_view_rate_p50", ""),
                mets.get("ad_video_view_rate_p75", ""), mets.get("ad_video_view_rate_p100", ""),
            ])
        if page >= d.get("data", {}).get("page_info", {}).get("total_page", 1):
            break
        page += 1
        time.sleep(0.3)
    return rows


def fetch_all(token, start_date, end_date):
    print("  캠페인 ID 수집 중...")
    campaign_ids = get_campaign_ids(token, start_date, end_date)
    print(f"  캠페인 {len(campaign_ids)}개 발견")
    all_rows = []
    for cid in campaign_ids:
        info = get_campaign_info(token, cid)
        cname = info.get("campaign_name", cid)
        gids = [str(g) for g in (info.get("item_group_ids") or [])]
        if not gids:
            continue
        print(f"  [{cname}] 소재 조회 중... ({len(gids)}개 그룹)")
        rows = fetch_item_rows(token, start_date, end_date, cid, gids, cname)
        all_rows.extend(rows)
        time.sleep(0.3)
    return all_rows


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
        sheet = spreadsheet.add_worksheet(title=SHEET_NAME, rows="10000", cols=str(len(HEADERS)))
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
    print(f"\n=== TikTok GMV MAX 광고소재 성과 [{start_date} ~ {end_date}] ===")
    token = get_token()
    rows = fetch_all(token, start_date, end_date)
    print(f"  총 {len(rows)}행 수집")
    save(rows)


if __name__ == "__main__":
    main()
