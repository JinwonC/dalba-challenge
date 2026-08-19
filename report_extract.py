"""33주차(8/10~8/16) vs 29주차(7/13~7/19) 주간보고 숫자 추출."""
from datetime import datetime, date

import gspread
from google.oauth2.service_account import Credentials

SA = "service_account.json"
US = "15dP91bH_skc7ZzcJ3ehH9H4IKCzSxcfuOcREr3OaL0o"
ADS = "1AhVPPUq6Npri72uhtFcOUVMBl1jA7nf2P0qDCDRRKfA"
INFLOW = "(중요,수동) 제품별 유입매출 RAW (520업데이트)"
BRANDLIVE = "(수동) 브랜드 라이브 RAW"

W33 = (date(2026, 8, 10), date(2026, 8, 16))
W29 = (date(2026, 7, 13), date(2026, 7, 19))


def num(x):
    s = str(x).replace(",", "").replace("$", "").replace("%", "").strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


def pdate(s):
    s = str(s).strip().replace(" ", "")
    for f in ("%Y.%m.%d", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(s[:10], f).date()
        except ValueError:
            try:
                return datetime.strptime(s, f).date()
            except ValueError:
                continue
    return None


def inweek(d, wk):
    return d and wk[0] <= d <= wk[1]


def main():
    creds = Credentials.from_service_account_file(
        SA, scopes=["https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/drive"])
    gc = gspread.authorize(creds)
    us = gc.open_by_key(US)

    # ── 유입매출 RAW ──
    inflow = us.worksheet(INFLOW).get_all_values()[1:]
    # 컬럼: 5 GMV, 6 SellerLIVE, 9 SellerVideo, 13 CreatorLIVE, 16 CreatorVideo,
    #       19 ProductCard, 20 Orders, 21 SKUorders, 23 Customers, 25 Impr, 26 Clicks
    CH = {"GMV": 5, "셀러라이브": 6, "셀러영상": 9, "AF라이브": 13,
          "AF영상": 16, "프로덕트카드": 19}
    def agg_store(wk):
        a = {k: 0.0 for k in CH}
        a.update(orders=0.0, sku=0.0, cust=0.0, impr=0.0, clk=0.0)
        for r in inflow:
            if not inweek(pdate(r[0]), wk):
                continue
            for k, i in CH.items():
                a[k] += num(r[i])
            a["orders"] += num(r[20]); a["sku"] += num(r[21])
            a["cust"] += num(r[23]); a["impr"] += num(r[25]); a["clk"] += num(r[26])
        return a

    for lbl, wk in [("33주차(8/10~16)", W33), ("29주차(7/13~19)", W29)]:
        a = agg_store(wk)
        cvr = a["sku"] / a["clk"] * 100 if a["clk"] else 0
        print(f"\n[스토어 {lbl}]")
        print(f"  GMV ${a['GMV']:,.0f} | 주문 {a['orders']:,.0f} | SKU주문 {a['sku']:,.0f} | 구매자 {a['cust']:,.0f}")
        print(f"  노출 {a['impr']:,.0f} | 클릭 {a['clk']:,.0f} | CVR(CTOR) {cvr:.2f}%")
        print(f"  채널: 셀러영상 ${a['셀러영상']:,.0f} | 프로덕트카드 ${a['프로덕트카드']:,.0f} | "
              f"셀러라이브 ${a['셀러라이브']:,.0f} | AF영상 ${a['AF영상']:,.0f} | AF라이브 ${a['AF라이브']:,.0f}")

    # 채널 증감
    a33, a29 = agg_store(W33), agg_store(W29)
    print("\n[채널 증감 33 vs 29]")
    for k in ["셀러영상", "프로덕트카드", "셀러라이브", "AF영상", "AF라이브"]:
        d = a33[k] - a29[k]
        pct = d / a29[k] * 100 if a29[k] else 0
        print(f"  {k}: ${a33[k]:,.0f} vs ${a29[k]:,.0f}  Δ${d:,.0f} ({pct:+.1f}%)")

    # ── 제품별 (유입매출 GMV 기준 상위) ──
    def prod_agg(wk):
        p = {}
        for r in inflow:
            if not inweek(pdate(r[0]), wk):
                continue
            key = (r[2], r[1][:45])  # (id, name)
            d = p.setdefault(key, {"gmv": 0, "sku": 0, "clk": 0, "cust": 0, "impr": 0})
            d["gmv"] += num(r[5]); d["sku"] += num(r[21]); d["clk"] += num(r[26])
            d["cust"] += num(r[23]); d["impr"] += num(r[25])
        return p
    p33, p29 = prod_agg(W33), prod_agg(W29)
    top = sorted(p33.items(), key=lambda kv: -kv[1]["gmv"])[:12]
    print("\n[제품별 상위 12 — 33주차 / (29주차)]")
    for (pid, name), d in top:
        d29 = p29.get((pid, name), {"gmv": 0, "sku": 0, "clk": 0, "cust": 0})
        cvr33 = d["sku"] / d["clk"] * 100 if d["clk"] else 0
        cvr29 = d29["sku"] / d29["clk"] * 100 if d29.get("clk") else 0
        print(f"  {name} [{pid}]")
        print(f"    GMV ${d['gmv']:,.0f} (29주 ${d29['gmv']:,.0f}) | 구매자 {d['cust']:,.0f} | "
              f"CVR {cvr33:.2f}%→(29주 {cvr29:.2f}%)")

    # ── 광고 (GMAX): 광고성과 ──
    ap = gc.open_by_key(ADS).worksheet("광고성과").get_all_values()[1:]
    # 0 날짜, 2 지출, 3 주문, 4 GMV, 5 ROI, 6 PRODUCT ID
    def ad_store(wk):
        spend = gmv = orders = 0.0
        byprod = {}
        for r in ap:
            if not inweek(pdate(r[0]), wk):
                continue
            s, g, o = num(r[2]), num(r[4]), num(r[3])
            spend += s; gmv += g; orders += o
            pid = r[6] if len(r) > 6 else ""
            bp = byprod.setdefault(pid, [0.0, 0.0])
            bp[0] += s; bp[1] += g
        return spend, gmv, orders, byprod
    s33, g33, o33, bp33 = ad_store(W33)
    s29, g29, o29, bp29 = ad_store(W29)
    print("\n[GMAX 광고 33 vs 29]")
    print(f"  광고비 ${s33:,.0f} vs ${s29:,.0f} (Δ{(s33-s29)/s29*100 if s29 else 0:+.1f}%)")
    print(f"  광고GMV ${g33:,.0f} vs ${g29:,.0f}")
    print(f"  ROI {g33/s33 if s33 else 0:.2f} vs {g29/s29 if s29 else 0:.2f}")
    print("\n[제품ID별 광고 33주차 상위]")
    for pid, (s, g) in sorted(bp33.items(), key=lambda kv: -kv[1][0])[:12]:
        s2, g2 = bp29.get(pid, [0, 0])
        print(f"  {pid}: 광고비 ${s:,.0f}(29주 ${s2:,.0f}) ROI {g/s if s else 0:.2f}(29주 {g2/s2 if s2 else 0:.2f})")

    # ── 브랜드 라이브 RAW ──
    bl = us.worksheet(BRANDLIVE).get_all_values()
    def bl_week(wk):
        tot = 0.0
        for r in bl:
            if not r or not inweek(pdate(r[0]), wk):
                continue
            tot += num(r[7]) if len(r) > 7 else 0
        return tot
    print("\n[브랜드라이브 RAW 주간 GMV(col7 합)]")
    print(f"  33주차 ${bl_week(W33):,.0f} | 29주차 ${bl_week(W29):,.0f}")


if __name__ == "__main__":
    main()
