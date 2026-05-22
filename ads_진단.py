"""TikTok Ads API 진단 - 캠페인 목록 + GMV MAX Store ID 확인"""
import requests, json, os

TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_tokens.json")
with open(TOKEN_FILE) as f:
    token = json.load(f)["access_token"]

ADVERTISER_ID = "7573855166672355345"
BASE = "https://business-api.tiktok.com/open_api/v1.3"
headers = {"Access-Token": token}

# 1. 전체 캠페인 목록
print("=" * 50)
print("전체 캠페인 목록 조회 중...")
r = requests.get(f"{BASE}/campaign/get/", headers=headers, params={
    "advertiser_id": ADVERTISER_ID,
    "page_size": 100,
    "filtering": json.dumps({"primary_status": "STATUS_ALL"}),
}, timeout=30)

data = r.json()
print(f"전체 캠페인 수: {data.get('data',{}).get('page_info',{}).get('total_number', 0)}")
for c in data.get("data", {}).get("list", []):
    print(f"  {c['campaign_name']}")
    print(f"    상태: {c['operation_status']} | 목표: {c.get('objective_type','')} | 생성: {c['create_time']}")

# 2. GMV MAX 연결된 Store ID 조회
print()
print("=" * 50)
print("GMV MAX Store ID 조회 중...")
r2 = requests.get(f"{BASE}/gmv_max/advertiser/store/get/", headers=headers, params={
    "advertiser_id": ADVERTISER_ID,
}, timeout=30)
d2 = r2.json()
print(f"Store 조회 결과: code={d2.get('code')}, msg={d2.get('message','')}")
print(json.dumps(d2.get("data", {}), indent=2, ensure_ascii=False))

# 3. 광고주 정보 조회
print()
print("=" * 50)
print("광고주 정보 조회 중...")
r3 = requests.get(f"{BASE}/advertiser/info/", headers=headers, params={
    "advertiser_ids": json.dumps([ADVERTISER_ID]),
}, timeout=30)
d3 = r3.json()
print(f"광고주 조회: code={d3.get('code')}")
for adv in d3.get("data", {}).get("list", []):
    print(f"  이름: {adv.get('name')}")
    print(f"  국가: {adv.get('country')}")
    print(f"  통화: {adv.get('currency')}")
    print(f"  timezone: {adv.get('timezone')}")
    # store 관련 필드가 있으면 출력
    for k, v in adv.items():
        if "store" in k.lower() or "shop" in k.lower():
            print(f"  [{k}]: {v}")
