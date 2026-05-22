"""GMV MAX item_group 엔드포인트 탐색"""
import requests, json, os

TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_tokens.json")
with open(TOKEN_FILE) as f:
    token = json.load(f)["access_token"]

ADVERTISER_ID = "7573855166672355345"
STORE_ID      = "7494221571082258140"
BASE = "https://business-api.tiktok.com/open_api/v1.3"
headers = {"Access-Token": token}

# 알려진 GMV MAX 캠페인 ID 하나 (리포트에서 확인된 것)
SAMPLE_CAMPAIGN_ID = "1855368265340113"

def call(path, params={}):
    try:
        r = requests.get(f"{BASE}{path}", headers=headers,
                         params={"advertiser_id": ADVERTISER_ID, **params}, timeout=30)
        return r.status_code, r.json()
    except Exception as e:
        return 0, {"error": str(e)}

print("=" * 50)
print(f"[1] adgroup/get - GMV MAX campaign_id 필터링 시도")
status, d = call("/adgroup/get/", {
    "page_size": 10,
    "filtering": json.dumps({
        "campaign_ids": [SAMPLE_CAMPAIGN_ID],
        "primary_status": "STATUS_ALL",
    })
})
print(f"  http={status}, code={d.get('code')}, msg={d.get('message')}")
print(f"  total={d.get('data',{}).get('page_info',{}).get('total_number',0)}")

print()
print("[2] GMV MAX 전용 adgroup/item_group 엔드포인트 탐색")
for path in [
    "/gmv_max/adgroup/get/",
    "/gmv_max/item_group/get/",
    "/gmv_max/ad/get/",
    "/campaign/gmv_max/item_group/list/",
]:
    status, d = call(path, {"page_size": 5,
                             "filtering": json.dumps({"campaign_ids": [SAMPLE_CAMPAIGN_ID]})})
    code = d.get("code", "?")
    msg  = d.get("message", "")[:80]
    total = d.get("data", {}).get("page_info", {}).get("total_number", "?")
    print(f"  {path}")
    print(f"    http={status}, code={code}, total={total}, msg={msg}")
    if code == 0:
        for item in (d.get("data", {}).get("list") or [])[:3]:
            print(f"      {item}")

print()
print("[3] campaign/gmv_max/info - campaign_id 포함해서 호출")
status, d = call("/campaign/gmv_max/info/", {"campaign_id": SAMPLE_CAMPAIGN_ID})
code = d.get("code", "?")
print(f"  http={status}, code={code}, msg={d.get('message','')}")
data = d.get("data") or {}
print(f"  data keys: {list(data.keys()) if isinstance(data, dict) else data}")

print()
print("[4] item_id 리포트를 item_group_ids 없이 campaign_ids만으로 시도")
try:
    r = requests.get(f"{BASE}/gmv_max/report/get/", headers=headers, params={
        "advertiser_id": ADVERTISER_ID,
        "store_ids": json.dumps([STORE_ID]),
        "dimensions": json.dumps(["stat_time_day", "item_id"]),
        "metrics": json.dumps(["cost", "orders", "gross_revenue", "roi"]),
        "start_date": "2026-05-01",
        "end_date": "2026-05-01",
        "filtering": json.dumps({"campaign_ids": [SAMPLE_CAMPAIGN_ID]}),
        "page": 1, "page_size": 5,
    }, timeout=30)
    d = r.json()
    print(f"  code={d.get('code')}, msg={d.get('message')}")
    print(f"  total={d.get('data',{}).get('page_info',{}).get('total_number',0)}")
    for item in (d.get("data",{}).get("list") or [])[:3]:
        print(f"    {item}")
except Exception as e:
    print(f"  오류: {e}")
