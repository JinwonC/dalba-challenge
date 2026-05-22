"""TikTok Ads API 진단 - 캠페인 목록 및 데이터 확인"""
import requests, json, os

TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_tokens.json")
with open(TOKEN_FILE) as f:
    token = json.load(f)["access_token"]

ADVERTISER_ID = "7573855166672355345"
BASE = "https://business-api.tiktok.com/open_api/v1.3"

headers = {"Access-Token": token}

# 1. 캠페인 목록 조회
print("[1] 캠페인 목록 조회...")
r = requests.get(f"{BASE}/campaign/get/", headers=headers, params={
    "advertiser_id": ADVERTISER_ID,
    "page_size": 10,
}, timeout=30)
print(json.dumps(r.json(), ensure_ascii=False, indent=2)[:3000])

# 2. 캠페인 레벨 리포트
print("\n[2] 캠페인 레벨 리포트 (2026-05-01 ~ 2026-05-20)...")
r2 = requests.get(f"{BASE}/report/integrated/get/", headers=headers, params={
    "advertiser_id": ADVERTISER_ID,
    "report_type": "BASIC",
    "data_level": "AUCTION_CAMPAIGN",
    "dimensions": json.dumps(["campaign_id", "stat_time_day"]),
    "metrics": json.dumps(["campaign_name", "spend", "impressions", "clicks"]),
    "start_date": "2026-05-01",
    "end_date": "2026-05-20",
    "page_size": 5,
}, timeout=30)
print(json.dumps(r2.json(), ensure_ascii=False, indent=2)[:3000])
