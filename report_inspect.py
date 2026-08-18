"""2차 탐색: 유입매출 RAW 전체 헤더/날짜커버리지/방문자컬럼, 광고성과 날짜, 브랜드라이브 헤더."""
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

SA = "service_account.json"
US = "15dP91bH_skc7ZzcJ3ehH9H4IKCzSxcfuOcREr3OaL0o"
ADS = "1AhVPPUq6Npri72uhtFcOUVMBl1jA7nf2P0qDCDRRKfA"
INFLOW = "(중요,수동) 제품별 유입매출 RAW (520업데이트)"
BRANDLIVE = "(수동) 브랜드 라이브 RAW"


def pdate(s):
    s = str(s).strip().replace(" ", "")
    for f in ("%Y.%m.%d", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(s[:10] if "-" in s or "/" in s else s, f).date()
        except ValueError:
            continue
    return None


def main():
    creds = Credentials.from_service_account_file(
        SA, scopes=["https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/drive"])
    gc = gspread.authorize(creds)
    us = gc.open_by_key(US)

    sh = us.worksheet(INFLOW)
    vals = sh.get_all_values()
    header = vals[0]
    print("[유입매출RAW] 전체 헤더 (인덱스:이름)")
    for i, h in enumerate(header):
        if h.strip():
            print(f"  {i}: {h.strip()[:40]}")
    # 방문자/visitor 컬럼 탐색
    vis = [i for i, h in enumerate(header) if any(k in h.lower() for k in ("visit", "방문"))]
    print(f"  → visitor 후보 컬럼: {vis}")

    # 날짜 커버리지
    dates = [pdate(r[0]) for r in vals[1:] if r and r[0].strip()]
    dates = [d for d in dates if d]
    if dates:
        print(f"  날짜: {min(dates)} ~ {max(dates)} (행 {len(dates)})")
    for label, a, b in [("W33", "2026-08-10", "2026-08-16"), ("W29", "2026-07-13", "2026-07-19")]:
        aa = datetime.strptime(a, "%Y-%m-%d").date()
        bb = datetime.strptime(b, "%Y-%m-%d").date()
        cnt = sum(1 for d in dates if aa <= d <= bb)
        print(f"  {label} {a}~{b}: {cnt}행")

    print("\n[광고성과] 날짜 커버리지")
    ap = gc.open_by_key(ADS).worksheet("광고성과").get_all_values()
    ad = [pdate(r[0]) for r in ap[1:] if r and r[0].strip()]
    ad = [d for d in ad if d]
    if ad:
        print(f"  {min(ad)} ~ {max(ad)} (행 {len(ad)})")

    print("\n[브랜드라이브RAW] 헤더")
    bl = us.worksheet(BRANDLIVE).get("A1:BZ3")
    for row in bl[:3]:
        print("  ", row[:12])


if __name__ == "__main__":
    main()
