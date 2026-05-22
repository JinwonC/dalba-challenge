"""GMV MAX campaign item_list에서 item_id → product_id 매핑 확인"""
import requests, json, os

TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_tokens.json")
with open(TOKEN_FILE) as f:
    token = json.load(f)["access_token"]

ADVERTISER_ID = "7573855166672355345"
BASE = "https://business-api.tiktok.com/open_api/v1.3"
headers = {"Access-Token": token}

CAMPAIGN_ID = "1855368265340113"

r = requests.get(f"{BASE}/campaign/gmv_max/info/", headers=headers,
                 params={"advertiser_id": ADVERTISER_ID, "campaign_id": CAMPAIGN_ID}, timeout=30)
data = r.json().get("data", {})

print(f"캠페인명: {data.get('campaign_name')}")
print()

item_list = data.get("item_list") or []
print(f"item_list 개수: {len(item_list)}")
print(f"첫 3개:")
for item in item_list[:3]:
    print(f"  {item}")

print()
print(f"item_list 전체 key 목록 (첫 항목 기준):")
if item_list:
    print(f"  {list(item_list[0].keys())}")

input("\n완료. 엔터 누르면 종료...")
