"""TikTok Ads API 진단 - GMV MAX 캠페인 탐색"""
import requests, json, os

TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_tokens.json")
with open(TOKEN_FILE) as f:
    token_data = json.load(f)

token = token_data["access_token"]
print(f"토큰에 연결된 advertiser_ids: {token_data.get('advertiser_ids', [])}")

BASE = "https://business-api.tiktok.com/open_api/v1.3"
headers = {"Access-Token": token}

# 토큰에 연결된 모든 광고주 계정 목록 확인
print()
print("=" * 50)
print("[1] 이 토큰으로 접근 가능한 광고주 계정 전체")
r = requests.get(f"{BASE}/oauth2/advertiser/get/", headers=headers, params={
    "app_id": "7641873128328101904",
    "secret": "4745bd7d6aad1b9a46dd05f1b20b006463e09962",
}, timeout=30)
d = r.json()
print(f"  code={d.get('code')}, msg={d.get('message')}")
for a in d.get("data", {}).get("list", []):
    print(f"  광고주: {a.get('advertiser_name')} | id={a.get('advertiser_id')} | status={a.get('status')}")

# 각 광고주 계정별로 캠페인 조회
advertiser_ids = token_data.get("advertiser_ids", ["7573855166672355345"])
print()
print("=" * 50)
print("[2] 각 광고주 계정별 캠페인 목록")
for adv_id in advertiser_ids:
    print(f"\n  [광고주 {adv_id}]")
    r = requests.get(f"{BASE}/campaign/get/", headers=headers, params={
        "advertiser_id": adv_id,
        "page_size": 100,
        "filtering": json.dumps({"primary_status": "STATUS_ALL"}),
    }, timeout=30)
    d = r.json()
    if d.get("code") == 0:
        for c in d.get("data", {}).get("list", []):
            print(f"    {c.get('campaign_name')} | id={c.get('campaign_id')} | objective={c.get('objective_type')} | status={c.get('operation_status')}")
    else:
        print(f"    오류: code={d.get('code')}, msg={d.get('message')}")

# GMV MAX 리포트 campaign_id 기준으로 직접 시도
print()
print("=" * 50)
print("[3] GMV MAX 리포트 campaign_id 기준 직접 시도 (2026-05-01)")
for adv_id in advertiser_ids:
    print(f"\n  [광고주 {adv_id}]")
    r = requests.get(f"{BASE}/gmv_max/report/get/", headers=headers, params={
        "advertiser_id": adv_id,
        "store_ids": json.dumps(["7494221571082258140"]),
        "dimensions": json.dumps(["stat_time_day", "campaign_id"]),
        "metrics": json.dumps(["cost", "orders", "gross_revenue", "roi"]),
        "start_date": "2026-05-01",
        "end_date": "2026-05-01",
        "page": 1,
        "page_size": 10,
    }, timeout=30)
    try:
        d = r.json()
        print(f"  code={d.get('code')}, msg={d.get('message')}")
        print(f"  총={d.get('data',{}).get('page_info',{}).get('total_number', 0)}행")
        for item in (d.get("data", {}).get("list") or []):
            print(f"    {item}")
    except Exception:
        print(f"  응답: {r.text[:300]}")
