"""TikTok Ads API 진단 - GMV MAX 캠페인/아이템그룹 ID 탐색"""
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
        return r.status_code, {"raw": r.text[:300]}

# 1. GMV MAX 전용 캠페인 엔드포인트 탐색
print("=" * 50)
print("[1] GMV MAX 캠페인 엔드포인트 탐색")
for path in ["/gmv_max/campaign/get/", "/gmv_max/campaigns/", "/campaign/get/"]:
    status, d = get(path, {"page_size": 10,
                            "filtering": json.dumps({"primary_status": "STATUS_ALL"})})
    code = d.get("code", "?")
    count = d.get("data", {}).get("page_info", {}).get("total_number", "?")
    print(f"  {path} → http={status}, code={code}, total={count}")
    if code == 0:
        for c in (d.get("data", {}).get("list") or []):
            print(f"    캠페인: {c.get('campaign_name')} | {c.get('campaign_id')} | {c.get('objective_type')}")

# 2. 아이템그룹(adgroup) 엔드포인트 탐색
print()
print("=" * 50)
print("[2] GMV MAX 아이템그룹 엔드포인트 탐색")
for path in ["/gmv_max/adgroup/get/", "/gmv_max/item_group/get/", "/adgroup/get/"]:
    status, d = get(path, {"page_size": 10,
                            "filtering": json.dumps({"primary_status": "STATUS_ALL"})})
    code = d.get("code", "?")
    count = d.get("data", {}).get("page_info", {}).get("total_number", "?")
    print(f"  {path} → http={status}, code={code}, total={count}")
    if code == 0:
        for g in (d.get("data", {}).get("list") or []):
            print(f"    그룹: {g.get('adgroup_name') or g.get('item_group_name')} | id={g.get('adgroup_id') or g.get('item_group_id')} | campaign={g.get('campaign_id')}")

# 3. campaign/get으로 전체 캠페인 (objective 확인)
print()
print("=" * 50)
print("[3] 전체 캠페인 목록 (objective_type 확인)")
status, d = get("/campaign/get/", {"page_size": 100,
                                    "filtering": json.dumps({"primary_status": "STATUS_ALL"})})
for c in (d.get("data", {}).get("list") or []):
    print(f"  {c.get('campaign_name')} | id={c.get('campaign_id')} | objective={c.get('objective_type')}")
