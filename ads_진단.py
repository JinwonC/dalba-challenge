"""GMV MAX item_id 리포트에서 product_id dimension 지원 여부 확인"""
import requests, json, os

TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_tokens.json")
with open(TOKEN_FILE) as f:
    token = json.load(f)["access_token"]

ADVERTISER_ID = "7573855166672355345"
STORE_ID      = "7494221571082258140"
BASE = "https://business-api.tiktok.com/open_api/v1.3"
headers = {"Access-Token": token}

CAMPAIGN_ID   = "1855368265340113"
ITEM_GROUP_ID = None  # 아래에서 자동 조회

# item_group_ids 가져오기
r = requests.get(f"{BASE}/campaign/gmv_max/info/", headers=headers,
                 params={"advertiser_id": ADVERTISER_ID, "campaign_id": CAMPAIGN_ID}, timeout=30)
info = r.json().get("data", {})
item_group_ids = [str(g) for g in (info.get("item_group_ids") or [])]
print(f"item_group_ids: {item_group_ids[:3]}")

if not item_group_ids:
    print("item_group_ids 없음 - 종료")
    exit()

# [1] product_id dimension 포함 시도
print()
print("[1] dimensions에 product_id 추가 시도")
r = requests.get(f"{BASE}/gmv_max/report/get/", headers=headers, params={
    "advertiser_id": ADVERTISER_ID,
    "store_ids": json.dumps([STORE_ID]),
    "dimensions": json.dumps(["stat_time_day", "item_id", "product_id"]),
    "metrics": json.dumps(["cost", "orders", "gross_revenue", "roi"]),
    "start_date": "2026-05-01", "end_date": "2026-05-01",
    "filtering": json.dumps({"campaign_ids": [CAMPAIGN_ID], "item_group_ids": item_group_ids[:5]}),
    "page": 1, "page_size": 3,
}, timeout=30)
d = r.json()
print(f"  code={d.get('code')}, msg={d.get('message')}")
for item in (d.get("data", {}).get("list") or [])[:3]:
    print(f"  dims keys: {list(item.get('dimensions', {}).keys())}")
    print(f"  {item}")

# [2] product_id 없이 item_id만 (기존 방식) - dimensions 확인
print()
print("[2] dimensions에 item_id만 (기존) - 응답에 product_id 있는지 확인")
r = requests.get(f"{BASE}/gmv_max/report/get/", headers=headers, params={
    "advertiser_id": ADVERTISER_ID,
    "store_ids": json.dumps([STORE_ID]),
    "dimensions": json.dumps(["stat_time_day", "item_id"]),
    "metrics": json.dumps(["cost", "orders", "gross_revenue", "roi"]),
    "start_date": "2026-05-01", "end_date": "2026-05-01",
    "filtering": json.dumps({"campaign_ids": [CAMPAIGN_ID], "item_group_ids": item_group_ids[:5]}),
    "page": 1, "page_size": 3,
}, timeout=30)
d = r.json()
print(f"  code={d.get('code')}, msg={d.get('message')}")
for item in (d.get("data", {}).get("list") or [])[:3]:
    print(f"  dims keys: {list(item.get('dimensions', {}).keys())}")
    print(f"  {item}")
