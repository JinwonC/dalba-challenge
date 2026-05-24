"""
Daily Slack Report: TikTok Shop + GMV MAX Ads 성과
- 전일 대비 GMV/주문수 비교
- 상품별 GMV 순위
- 크리에이터 성과
- GMV MAX 광고 성과 (PID 매칭)
- 핵심 인사이트

환경변수:
  SLACK_WEBHOOK_URL  - Slack Incoming Webhook URL
  SERVICE_ACCOUNT_JSON - Google service account JSON (문자열)
  ADS_TOKENS_JSON    - TikTok Ads access token JSON (문자열)
"""
import json, os, time, sys, base64, subprocess, urllib.request, urllib.parse
import requests
from datetime import datetime, timedelta, timezone
from collections import defaultdict

# ──────────────────────────────────────────
# 설정
# ──────────────────────────────────────────
SLACK_WEBHOOK_URL   = os.environ.get("SLACK_WEBHOOK_URL", "")
SPREADSHEET_ID      = "15dP91bH_skc7ZzcJ3ehH9H4IKCzSxcfuOcREr3OaL0o"
ADS_SPREADSHEET_ID  = "1AhVPPUq6Npri72uhtFcOUVMBl1jA7nf2P0qDCDRRKfA"
ADVERTISER_ID       = "7573855166672355345"
STORE_ID            = "7494221571082258140"
BASE_ADS            = "https://business-api.tiktok.com/open_api/v1.3"
GMV_REPORT_URL      = f"{BASE_ADS}/gmv_max/report/get/"

SA_FILE = "/tmp/slack_sa.json"
ADS_TOKEN_FILE = "/tmp/slack_ads_tokens.json"


# ──────────────────────────────────────────
# 인증
# ──────────────────────────────────────────
def setup_credentials():
    sa_json = os.environ.get("SERVICE_ACCOUNT_JSON", "")
    if sa_json:
        with open(SA_FILE, "w") as f:
            f.write(sa_json)
    ads_json = os.environ.get("ADS_TOKENS_JSON", "")
    if ads_json:
        with open(ADS_TOKEN_FILE, "w") as f:
            f.write(ads_json)


def get_sheets_token():
    with open(SA_FILE) as f:
        sa = json.load(f)
    now = int(time.time())
    header = base64.urlsafe_b64encode(json.dumps({"alg": "RS256", "typ": "JWT"}).encode()).rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(json.dumps({
        "iss": sa["client_email"],
        "scope": "https://www.googleapis.com/auth/spreadsheets.readonly",
        "aud": "https://oauth2.googleapis.com/token",
        "exp": now + 3600, "iat": now,
    }).encode()).rstrip(b"=").decode()
    signing_input = f"{header}.{payload}"
    pk_file = "/tmp/slack_pk.pem"
    with open(pk_file, "w") as f:
        f.write(sa["private_key"])
    result = subprocess.run(
        ["openssl", "dgst", "-sha256", "-sign", pk_file],
        input=signing_input.encode(), capture_output=True
    )
    sig = base64.urlsafe_b64encode(result.stdout).rstrip(b"=").decode()
    jwt_token = f"{signing_input}.{sig}"
    data = urllib.parse.urlencode({
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": jwt_token,
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())["access_token"]


def get_ads_token():
    with open(ADS_TOKEN_FILE) as f:
        return json.load(f).get("access_token", "")


def read_sheet(token, spreadsheet_id, sheet_name):
    encoded = urllib.parse.quote(sheet_name)
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{encoded}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read()).get("values", [])


# ──────────────────────────────────────────
# 유틸
# ──────────────────────────────────────────
def safe_float(v):
    try: return float(str(v).replace(",", ""))
    except: return 0.0

def safe_int(v):
    try: return int(str(v).replace(",", ""))
    except: return 0

def pct_str(new, old):
    if old == 0:
        return "(신규)" if new > 0 else ""
    d = (new - old) / old * 100
    arrow = "▲" if d > 0 else "▼"
    return f"{arrow}{abs(d):.1f}%"

def arrow(new, old):
    if old == 0: return "🆕"
    d = new - old
    if d > 0: return "🔺"
    if d < 0: return "🔻"
    return "➡️"

def fmt_usd(v):
    return f"${v:,.2f}"

def short_name(name, max_len=28):
    name = name.replace("[OFFICIAL d'Alba] ", "").replace("[d'Alba] ", "").replace("[Set] ", "Set ")
    return name[:max_len] + "…" if len(name) > max_len else name


# ──────────────────────────────────────────
# 날짜 계산 (LA 기준)
# ──────────────────────────────────────────
def get_report_dates():
    """LA 시간 기준 어제/그제"""
    la_offset = timedelta(hours=-7)  # PDT (여름)
    now_la = datetime.now(timezone.utc) + la_offset
    today_la = now_la.date()
    report_date = today_la - timedelta(days=1)    # 어제
    compare_date = today_la - timedelta(days=2)   # 그제
    return str(report_date), str(compare_date)


# ──────────────────────────────────────────
# Google Sheets 데이터 수집
# ──────────────────────────────────────────
def fetch_sku_data(sheets_token, date_str):
    """SKU Order 탭에서 특정 날짜 데이터"""
    rows = read_sheet(sheets_token, SPREADSHEET_ID, "(중요, 자동) SKU Order")
    result = defaultdict(lambda: {"orders": 0, "qty": 0, "gmv": 0.0, "skus": {}})
    for row in rows[1:]:
        if not row or not str(row[0]).startswith(date_str): continue
        if len(row) < 6: continue
        pid = str(row[1])
        sku = str(row[2])
        orders = safe_int(row[3])
        qty = safe_int(row[4])
        gmv = safe_float(row[5])
        result[pid]["orders"] += orders
        result[pid]["qty"] += qty
        result[pid]["gmv"] += gmv
        if sku not in result[pid]["skus"]:
            result[pid]["skus"][sku] = {"orders": 0, "qty": 0, "gmv": 0.0}
        result[pid]["skus"][sku]["orders"] += orders
        result[pid]["skus"][sku]["qty"] += qty
        result[pid]["skus"][sku]["gmv"] += gmv
    return result


def fetch_af_data(sheets_token, date_str):
    """주문별 AF RAW 탭에서 특정 날짜 (날짜형식: '2026. 5. 19')"""
    rows = read_sheet(sheets_token, SPREADSHEET_ID, "(중요,수동) 주문별 AF 매출 RAW")
    # 날짜 변환: "2026-05-19" → "2026. 5. 19"
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    korean_date = f"{dt.year}. {dt.month}. {dt.day}"

    creators = defaultdict(lambda: {"orders": 0, "amount": 0.0, "qty": 0})
    by_type = defaultdict(int)
    total_amount = 0.0
    total_orders = 0
    pid_names = {}

    for row in rows[1:]:
        if not row or str(row[0]).strip() != korean_date: continue
        total_orders += 1
        amt = safe_float(row[6]) if len(row) > 6 else 0
        qty = safe_int(row[8]) if len(row) > 8 else 0
        total_amount += amt
        creator = row[12] if len(row) > 12 else "Unknown"
        creators[creator]["orders"] += 1
        creators[creator]["amount"] += amt
        creators[creator]["qty"] += qty
        ct = row[13] if len(row) > 13 else "Unknown"
        by_type[ct] += 1
        pid = row[2] if len(row) > 2 else ""
        pname = row[3] if len(row) > 3 else ""
        if pid and pname:
            pid_names[pid] = pname

    return {
        "total_orders": total_orders,
        "total_amount": total_amount,
        "creators": dict(creators),
        "by_type": dict(by_type),
        "pid_names": pid_names,
    }


# ──────────────────────────────────────────
# TikTok Ads API 데이터 수집
# ──────────────────────────────────────────
def api_get(ads_token, params, retries=3):
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(GMV_REPORT_URL,
                             headers={"Access-Token": ads_token},
                             params=params, timeout=30)
            d = r.json()
            if d.get("code") == 0:
                return d
            if d.get("code") == 40002:
                return None
        except Exception as e:
            print(f"  [광고API 오류] {e} (시도 {attempt})")
        time.sleep(2 * attempt)
    return None


def fetch_ads_by_pid(ads_token, date_str):
    """GMV MAX 리포트에서 item_id(PID)별 광고 성과"""
    result = defaultdict(lambda: {"cost": 0.0, "orders": 0, "gmv": 0.0, "roi": 0.0, "rows": 0})
    page = 1
    while True:
        d = api_get(ads_token, {
            "advertiser_id": ADVERTISER_ID,
            "store_ids": json.dumps([STORE_ID]),
            "dimensions": json.dumps(["stat_time_day", "item_id"]),
            "metrics": json.dumps(["cost", "orders", "gross_revenue", "roi"]),
            "start_date": date_str, "end_date": date_str,
            "page": page, "page_size": 1000,
        })
        if not d: break
        for item in d.get("data", {}).get("list", []):
            dims = item.get("dimensions", {})
            mets = item.get("metrics", {})
            cost = safe_float(mets.get("cost"))
            gmv  = safe_float(mets.get("gross_revenue"))
            if cost == 0 and gmv == 0: continue
            pid = dims.get("item_id", "")
            if pid == "-1": pid = "프로덕트카드"
            result[pid]["cost"]   += cost
            result[pid]["orders"] += safe_int(mets.get("orders"))
            result[pid]["gmv"]    += gmv
            result[pid]["rows"]   += 1
            # roi is a rate; average it
            result[pid]["roi"]     = safe_float(mets.get("roi")) if result[pid]["rows"] == 1 else \
                                     (result[pid]["roi"] + safe_float(mets.get("roi"))) / 2
        pi = d.get("data", {}).get("page_info", {})
        if page >= pi.get("total_page", 1): break
        page += 1
        time.sleep(0.3)
    return dict(result)


# ──────────────────────────────────────────
# Slack 메시지 구성
# ──────────────────────────────────────────
def build_slack_blocks(report_date, compare_date,
                       sku_today, sku_yesterday,
                       af_today, af_yesterday,
                       ads_today, ads_yesterday,
                       pid_names):

    gmv_t  = sum(v["gmv"] for v in sku_today.values())
    gmv_y  = sum(v["gmv"] for v in sku_yesterday.values())
    ord_t  = sum(v["orders"] for v in sku_today.values())
    ord_y  = sum(v["orders"] for v in sku_yesterday.values())
    qty_t  = sum(v["qty"] for v in sku_today.values())
    qty_y  = sum(v["qty"] for v in sku_yesterday.values())

    af_t   = af_today["total_orders"]
    af_y   = af_yesterday["total_orders"]
    af_amt_t = af_today["total_amount"]
    af_amt_y = af_yesterday["total_amount"]

    ads_cost_t = sum(v["cost"] for v in ads_today.values())
    ads_cost_y = sum(v["cost"] for v in ads_yesterday.values())
    ads_gmv_t  = sum(v["gmv"] for v in ads_today.values())
    ads_gmv_y  = sum(v["gmv"] for v in ads_yesterday.values())
    ads_roi_t  = (ads_gmv_t / ads_cost_t) if ads_cost_t > 0 else 0
    ads_roi_y  = (ads_gmv_y / ads_cost_y) if ads_cost_y > 0 else 0

    # Format date nicely
    dt = datetime.strptime(report_date, "%Y-%m-%d")
    date_label = f"{dt.month}월 {dt.day}일"
    dt2 = datetime.strptime(compare_date, "%Y-%m-%d")
    date2_label = f"{dt2.month}월 {dt2.day}일"

    blocks = []

    # ── 헤더 ──
    blocks.append({
        "type": "header",
        "text": {"type": "plain_text", "text": f"📊 d'Alba TikTok Shop 일일 리포트 — {date_label}"}
    })
    blocks.append({"type": "divider"})

    # ── 1. 전체 요약 ──
    gmv_delta = gmv_t - gmv_y
    gmv_pct = pct_str(gmv_t, gmv_y)
    ord_pct = pct_str(ord_t, ord_y)
    af_pct = pct_str(af_t, af_y)

    summary_lines = [
        f"*🏪 전체 Shop GMV*: {fmt_usd(gmv_t)}  {arrow(gmv_t, gmv_y)} {gmv_pct}  _(전일 {fmt_usd(gmv_y)})_",
        f"*📦 SKU 주문수*: {ord_t:,}건  {arrow(ord_t, ord_y)} {ord_pct}  _(전일 {ord_y:,}건)_",
        f"*📦 판매수량*: {qty_t:,}개  {arrow(qty_t, qty_y)} {pct_str(qty_t, qty_y)}",
        f"*🤝 AF 주문*: {af_t:,}건 / {fmt_usd(af_amt_t)}  {arrow(af_t, af_y)} {af_pct}",
        f"*📣 광고비*: {fmt_usd(ads_cost_t)}  {arrow(ads_cost_t, ads_cost_y)} {pct_str(ads_cost_t, ads_cost_y)}  |  *광고 GMV*: {fmt_usd(ads_gmv_t)}  |  *ROI*: {ads_roi_t:.2f}x  {arrow(ads_roi_t, ads_roi_y)} {pct_str(ads_roi_t, ads_roi_y)}",
    ]
    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": "*1️⃣ 전체 요약*\n" + "\n".join(summary_lines)}
    })
    blocks.append({"type": "divider"})

    # ── 2. 상품별 GMV 순위 (Top 10) ──
    all_pids = set(list(sku_today.keys()) + list(sku_yesterday.keys()))
    pid_list = sorted(all_pids, key=lambda p: sku_today.get(p, {}).get("gmv", 0), reverse=True)

    lines = ["```", f"{'#':<3} {'상품명':<28} {'어제':>8} {'오늘':>8} {'증감':>8}", "-" * 60]
    for i, pid in enumerate(pid_list[:10], 1):
        g_t = sku_today.get(pid, {}).get("gmv", 0)
        g_y = sku_yesterday.get(pid, {}).get("gmv", 0)
        name = short_name(pid_names.get(pid, pid))
        delta = g_t - g_y
        delta_str = f"{delta:+,.0f}" if g_y > 0 else "신규"
        lines.append(f"{i:<3} {name:<28} {g_y:>8,.0f} {g_t:>8,.0f} {delta_str:>8}")
    lines.append("```")

    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": "*2️⃣ 상품별 GMV 순위 Top 10 (USD)*\n" + "\n".join(lines)}
    })
    blocks.append({"type": "divider"})

    # ── 3. 크리에이터 성과 Top 10 ──
    all_creators = set(list(af_today["creators"].keys()) + list(af_yesterday["creators"].keys()))
    cr_list = sorted(all_creators,
                     key=lambda c: af_today["creators"].get(c, {}).get("orders", 0),
                     reverse=True)

    lines = ["```", f"{'크리에이터':<25} {'전일 주문':>8} {'당일 주문':>8} {'당일 금액':>10}", "-" * 55]
    for c in cr_list[:10]:
        o_t = af_today["creators"].get(c, {}).get("orders", 0)
        o_y = af_yesterday["creators"].get(c, {}).get("orders", 0)
        a_t = af_today["creators"].get(c, {}).get("amount", 0)
        lines.append(f"{'@'+str(c)[:24]:<25} {o_y:>8,} {o_t:>8,} {a_t:>10,.2f}")
    lines.append("```")

    # 신규 크리에이터 하이라이트
    new_cr = [(c, af_today["creators"][c]["orders"], af_today["creators"][c]["amount"])
              for c in all_creators
              if c not in af_yesterday["creators"] and af_today["creators"].get(c, {}).get("orders", 0) > 0]
    new_cr.sort(key=lambda x: x[2], reverse=True)
    if new_cr[:3]:
        new_line = "  🆕 신규: " + "  |  ".join([f"@{c} {o}건/${a:,.0f}" for c, o, a in new_cr[:3]])
        lines.append(new_line)

    # 콘텐츠 유형 breakdown
    type_parts = []
    for ct, cnt in sorted(af_today["by_type"].items(), key=lambda x: -x[1]):
        y_cnt = af_yesterday["by_type"].get(ct, 0)
        type_parts.append(f"{ct}: {cnt}건 ({cnt-y_cnt:+})")
    if type_parts:
        lines.append(f"  📌 유형별: {' | '.join(type_parts)}")

    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": "*3️⃣ 크리에이터 AF 성과 Top 10*\n" + "\n".join(lines)}
    })
    blocks.append({"type": "divider"})

    # ── 4. GMV MAX 광고 성과 (PID별) ──
    all_ad_pids = set(list(ads_today.keys()) + list(ads_yesterday.keys()))
    ad_list = sorted(all_ad_pids,
                     key=lambda p: ads_today.get(p, {}).get("gmv", 0),
                     reverse=True)

    lines = ["```",
             f"{'상품명':<28} {'광고비':>8} {'광고GMV':>8} {'ROI':>6} {'증감ROI':>8}",
             "-" * 62]
    for pid in ad_list[:10]:
        d_t = ads_today.get(pid, {})
        d_y = ads_yesterday.get(pid, {})
        cost_t = d_t.get("cost", 0)
        gmv_t_ad = d_t.get("gmv", 0)
        roi_t = (gmv_t_ad / cost_t) if cost_t > 0 else 0
        roi_y = d_y.get("roi", 0) if d_y else 0
        name = short_name(pid_names.get(pid, pid))
        roi_delta = roi_t - roi_y
        lines.append(f"{name:<28} {cost_t:>8,.0f} {gmv_t_ad:>8,.0f} {roi_t:>6.2f} {roi_delta:>+8.2f}")
    lines.append("```")

    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": "*4️⃣ GMV MAX 광고 성과 (PID별)*\n" + "\n".join(lines)}
    })
    blocks.append({"type": "divider"})

    # ── 5. 핵심 인사이트 ──
    insights = []

    # GMV trend
    if gmv_t > gmv_y:
        insights.append(f"✅ Shop GMV *{gmv_pct}* 성장. 광고 ROI {ads_roi_t:.2f}x (전일 {ads_roi_y:.2f}x).")
    else:
        insights.append(f"⚠️ Shop GMV *{gmv_pct}* 감소. 원인 점검 필요.")

    # Best product
    if pid_list:
        best = pid_list[0]
        best_gmv = sku_today.get(best, {}).get("gmv", 0)
        best_name = short_name(pid_names.get(best, best))
        insights.append(f"🏆 GMV 1위: *{best_name}* ({fmt_usd(best_gmv)})")

    # Most improved product
    improved = sorted(all_pids,
                      key=lambda p: sku_today.get(p, {}).get("gmv", 0) - sku_yesterday.get(p, {}).get("gmv", 0),
                      reverse=True)
    if improved:
        top_imp = improved[0]
        imp_delta = sku_today.get(top_imp, {}).get("gmv", 0) - sku_yesterday.get(top_imp, {}).get("gmv", 0)
        if imp_delta > 0:
            imp_name = short_name(pid_names.get(top_imp, top_imp))
            insights.append(f"📈 최대 성장 상품: *{imp_name}* (+{fmt_usd(imp_delta)})")

    # Biggest drop
    dropped = sorted(all_pids,
                     key=lambda p: sku_today.get(p, {}).get("gmv", 0) - sku_yesterday.get(p, {}).get("gmv", 0))
    if dropped:
        top_drop = dropped[0]
        drop_delta = sku_today.get(top_drop, {}).get("gmv", 0) - sku_yesterday.get(top_drop, {}).get("gmv", 0)
        if drop_delta < 0:
            drop_name = short_name(pid_names.get(top_drop, top_drop))
            insights.append(f"📉 최대 하락 상품: *{drop_name}* ({fmt_usd(drop_delta)})")

    # AF vs total discrepancy
    if af_t < af_y and gmv_t > gmv_y:
        insights.append("💡 AF 주문은 줄었지만 Shop GMV는 증가 — 자체 채널(라이브/광고) 기여 상승 가능성.")

    # New creators
    if new_cr:
        insights.append(f"🆕 신규 크리에이터 *{len(new_cr)}명* 첫 주문 발생.")

    # Best ROI ad product
    if ad_list:
        best_roi_pid = max(ads_today.keys(), key=lambda p: ads_today[p].get("gmv", 0) / ads_today[p].get("cost", 1) if ads_today[p].get("cost", 0) > 0 else 0)
        br_cost = ads_today[best_roi_pid].get("cost", 0)
        br_gmv = ads_today[best_roi_pid].get("gmv", 0)
        br_roi = (br_gmv / br_cost) if br_cost > 0 else 0
        if br_roi > 0:
            br_name = short_name(pid_names.get(best_roi_pid, best_roi_pid))
            insights.append(f"💰 광고 ROI 최고 상품: *{br_name}* (ROI {br_roi:.2f}x)")

    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": "*5️⃣ 핵심 인사이트*\n" + "\n".join(f"• {i}" for i in insights)}
    })

    # ── 푸터 ──
    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": f"📅 기준일: {date_label} vs {date2_label} (LA 시간)  |  자동 생성 by GitHub Actions"}]
    })

    return blocks


# ──────────────────────────────────────────
# 메인
# ──────────────────────────────────────────
def main():
    if not SLACK_WEBHOOK_URL:
        print("❌ SLACK_WEBHOOK_URL 환경변수 없음")
        sys.exit(1)

    setup_credentials()

    report_date, compare_date = get_report_dates()
    print(f"📊 리포트 날짜: {report_date} vs {compare_date}")

    print("  Google Sheets 인증 중...")
    sheets_token = get_sheets_token()

    print("  SKU Order 데이터 수집 중...")
    sku_today = fetch_sku_data(sheets_token, report_date)
    sku_yesterday = fetch_sku_data(sheets_token, compare_date)

    print("  AF 주문 데이터 수집 중...")
    af_today = fetch_af_data(sheets_token, report_date)
    af_yesterday = fetch_af_data(sheets_token, compare_date)

    # PID → 상품명 통합
    pid_names = {}
    pid_names.update(af_today.get("pid_names", {}))
    pid_names.update(af_yesterday.get("pid_names", {}))

    print("  GMV MAX 광고 데이터 수집 중...")
    ads_token = get_ads_token()
    ads_today = fetch_ads_by_pid(ads_token, report_date)
    ads_yesterday = fetch_ads_by_pid(ads_token, compare_date)

    print("  Slack 메시지 구성 중...")
    blocks = build_slack_blocks(
        report_date, compare_date,
        sku_today, sku_yesterday,
        af_today, af_yesterday,
        ads_today, ads_yesterday,
        pid_names,
    )

    payload = {"blocks": blocks}
    resp = requests.post(SLACK_WEBHOOK_URL,
                         headers={"Content-Type": "application/json"},
                         data=json.dumps(payload), timeout=15)

    if resp.status_code == 200:
        print("  ✅ Slack 리포트 전송 완료")
    else:
        print(f"  ❌ Slack 전송 실패: {resp.status_code} {resp.text}")
        sys.exit(1)


if __name__ == "__main__":
    main()
