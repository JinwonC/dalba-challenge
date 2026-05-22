"""TikTok Ads API 진단 - GMV MAX 캠페인 탐색"""
import requests, json, os

TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_tokens.json")
with open(TOKEN_FILE) as f:
    token = json.load(f)["access_token"]

ADVERTISER_ID = "7573855166672355345"
BASE = "https://business-api.tiktok.com/open_api/v1.3"
headers = {"Access-Token": token}

def get(path, params={}):
    r = requests.get(f"{BASE}{path}", headers=headers,
                     params={"advertiser_id": ADVERTISER_ID, **params}, timeout=30)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"raw": r.text[:500]}

# 1. 모든 status + 모든 objective로 캠페인 전체 조회
print("=" * 50)
print("[1] 캠페인 전체 목록 (status 구분 없이)")
for status_filter in ["STATUS_ALL", "STATUS_ENABLE", "STATUS_DISABLE", "STATUS_DELETE"]:
    _, d = get("/campaign/get/", {"page_size": 100, "filtering": json.dumps({"primary_status": status_filter})})
    campaigns = d.get("data", {}).get("list", [])
    if campaigns:
        print(f"\n  [{status_filter}] {len(campaigns)}개:")
        for c in campaigns:
            print(f"    {c.get('campaign_name')} | id={c.get('campaign_id')} | objective={c.get('objective_type')} | status={c.get('operation_status')}")

# 2. GMV MAX 전용 캠페인 엔드포인트 여러 방식 시도
print()
print("=" * 50)
print("[2] GMV MAX 전용 엔드포인트 시도")
for path in [
    "/gmv_max/campaign/get/",
    "/campaign/get/",
]:
    for obj_type in ["PRODUCT_SALES", "SHOP_PURCHASES", "GMV_MAX", "RF_REACH"]:
        _, d = get(path, {
            "page_size": 10,
            "filtering": json.dumps({"primary_status": "STATUS_ALL", "objective_type": obj_type})
        })
        code = d.get("code", "?")
        count = d.get("data", {}).get("page_info", {}).get("total_number", 0)
        if count and count != "?":
            print(f"  {path} objective={obj_type} → {count}개 발견!")
            for c in d.get("data", {}).get("list", []):
                print(f"    {c.get('campaign_name')} | id={c.get('campaign_id')}")

# 3. 광고주 정보에서 GMV MAX 관련 권한 확인
print()
print("=" * 50)
print("[3] 광고주 정보")
_, d = get("/advertiser/info/", {"fields": json.dumps(["name", "status", "currency", "advertiser_id"])})
if d.get("code") == 0:
    for a in d.get("data", {}).get("list", []):
        print(f"  {a}")

# 4. GMV MAX 리포트를 campaign_id 기준으로 직접 시도 (필터 없이)
print()
print("=" * 50)
print("[4] GMV MAX 리포트 campaign_id 기준 직접 시도 (2026-05-01)")
_, d = requests.get(f"{BASE}/gmv_max/report/get/", headers=headers, params={
    "advertiser_id": ADVERTISER_ID,
    "store_ids": json.dumps(["7494221571082258140"]),
    "dimensions": json.dumps(["stat_time_day", "campaign_id"]),
    "metrics": json.dumps(["cost", "orders", "gross_revenue", "roi"]),
    "start_date": "2026-05-01",
    "end_date": "2026-05-01",
    "page": 1,
    "page_size": 10,
}, timeout=30).json(), None
print(f"  code={d.get('code')}, msg={d.get('message')}")
print(f"  총={d.get('data',{}).get('page_info',{}).get('total_number', 0)}행")
for item in d.get("data", {}).get("list", []):
    print(f"    {item}")
