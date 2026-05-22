"""TikTok Ads API 진단 - 전체 캠페인 목록 확인"""
import requests, json, os

TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_tokens.json")
with open(TOKEN_FILE) as f:
    token = json.load(f)["access_token"]

ADVERTISER_ID = "7573855166672355345"
BASE = "https://business-api.tiktok.com/open_api/v1.3"
headers = {"Access-Token": token}

print("전체 캠페인 목록 조회 중...")
r = requests.get(f"{BASE}/campaign/get/", headers=headers, params={
    "advertiser_id": ADVERTISER_ID,
    "page_size": 100,
    "filtering": json.dumps({"primary_status": "STATUS_ALL"}),
}, timeout=30)

data = r.json()
print(f"전체 캠페인 수: {data.get('data',{}).get('page_info',{}).get('total_number', 0)}")
print()
for c in data.get("data", {}).get("list", []):
    print(f"  {c['campaign_name']}")
    print(f"    상태: {c['operation_status']} | 목표: {c.get('objective_type','')} | 스마트: {c.get('is_smart_performance_campaign','')} | 생성: {c['create_time']}")
