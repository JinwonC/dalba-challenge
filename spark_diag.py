"""진단: 토큰이 접근 가능한 advertiser 목록과, 각 계정의 AUCTION(Spark/Consideration)
광고 데이터 존재 여부를 확인한다. (스파크애즈 적재용 advertiser_id 찾기)
"""
import json
import os

import requests

TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_tokens.json")
BASE = "https://business-api.tiktok.com/open_api/v1.3"

START = "2026-06-15"
END = "2026-07-14"


def load_token():
    with open(TOKEN_FILE) as f:
        t = json.load(f)
    return t.get("access_token", ""), t.get("advertiser_ids", []), t.get("scope", [])


def advertiser_names(token, ids):
    r = requests.get(
        f"{BASE}/advertiser/info/",
        headers={"Access-Token": token},
        params={"advertiser_ids": json.dumps(ids), "fields": json.dumps(["advertiser_id", "advertiser_name"])},
        timeout=30,
    )
    return r.json()


def count_auction(token, adv_id, data_level):
    r = requests.get(
        f"{BASE}/report/integrated/get/",
        headers={"Access-Token": token},
        params={
            "advertiser_id": adv_id,
            "report_type": "BASIC",
            "data_level": data_level,
            "dimensions": json.dumps(["campaign_id", "stat_time_day"]),
            "metrics": json.dumps(["spend", "impressions", "campaign_name"]),
            "start_date": START,
            "end_date": END,
            "page": 1,
            "page_size": 10,
            "lifetime": "false",
        },
        timeout=30,
    )
    d = r.json()
    code = d.get("code")
    if code != 0:
        return f"code={code} msg={d.get('message')}"
    info = d.get("data", {}).get("page_info", {})
    total = info.get("total_number", 0)
    sample = d.get("data", {}).get("list", [])[:3]
    names = [s.get("metrics", {}).get("campaign_name", "") for s in sample]
    return f"total={total} 샘플캠페인={names}"


def main():
    token, ids, scope = load_token()
    print(f"scope = {scope}")
    print(f"advertiser_ids = {ids}\n")

    print("=== advertiser 이름 ===")
    print(json.dumps(advertiser_names(token, ids), ensure_ascii=False, indent=2)[:2000])

    print(f"\n=== 각 계정 AUCTION 데이터 ({START}~{END}) ===")
    for adv in ids:
        ad = count_auction(token, adv, "AUCTION_AD")
        camp = count_auction(token, adv, "AUCTION_CAMPAIGN")
        print(f"[{adv}] AUCTION_AD: {ad}")
        print(f"[{adv}] AUCTION_CAMPAIGN: {camp}")


if __name__ == "__main__":
    main()
