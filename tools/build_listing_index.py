#!/usr/bin/env python3
"""리스팅 시트들을 읽어 크리에이터 중복체크용 인덱스를 만든다.

소스가 세 개다.
  - d'Alba Onboarding      : 지금까지의 리스팅 이력 ("(new) ..." 탭 + 인하우스 로스터)
  - d'Alba_Pickdi_Process  : 현재 쓰는 제품별 탭 (firstsprayserum, multibalm, ... , 07_comfrt)
  - 유가 인원 정리          : 유가 협업 현황 (캐스팅 / 담당자 / Flat fee / PAID 성과 / VIP Creator)
담당자들이 구 시트에서 신 시트로 일부만 옮겨 담았기 때문에 앞의 둘을 같이 봐야 중복이 제대로 잡히고,
유가 시트를 봐야 "이미 돈 주고 협업 중인 사람에게 또 리치아웃하는" 사고를 막을 수 있다.

레포가 public이므로 크리에이터 핸들은 평문으로 커밋하지 않는다.
페이로드를 gzip → AES-GCM 암호화해 data/listings.enc.json 으로 저장하고,
브라우저에서 팀 패스코드로만 복호화한다. 이메일은 아예 담지 않는다.

    python tools/build_listing_index.py
    python tools/build_listing_index.py --fixture tools/fixtures/sample.json   # 자격증명 없이 검증

읽을 시트·탭은 아래 SOURCES / PAID_TAB_PATTERNS 에 있다.

환경변수
    SERVICE_ACCOUNT_FILE  기본 service_account.json
    LISTING_PASSCODE      암호화 패스코드 (팀 공용)
"""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# 유가 시트에서 읽을 탭. 이 시트는 26개 탭 중 대부분이 성과·정산·배송용이고,
# 주소 폼 응답처럼 실명·집주소·전화번호가 든 탭도 있어서 화이트리스트로만 읽는다.
# 값은 판정 등급 — partner(이미 협업 중) / casting(제안·아웃리치 보냄).
PAID_TAB_PATTERNS = [
    (re.compile(r"캐스팅"), "casting"),
    (re.compile(r"담당자"), "partner"),
    (re.compile(r"flat\s*fee", re.I), "partner"),
    (re.compile(r"성과\s*트래킹"), "partner"),
    (re.compile(r"vip\s*creator", re.I), "partner"),
]

# mode="auto"  : 핸들 + Listed Date 컬럼이 있는 탭을 전부 리스팅 탭으로 인식 (새 제품 탭 자동 대응)
# mode="named" : PAID_TAB_PATTERNS에 걸리는 탭만 읽음
SOURCES = [
    {"id": "1Bhi85hXhIOHfWu9419drpeOuCOPXRkfMrW-4l_pJRB0", "mode": "auto"},   # d'Alba Onboarding
    {"id": "1ZtATip5Ul8cahN80-Oj-TyKb_UkLPBB67RKfnFRumr8", "mode": "auto"},   # d'Alba_Pickdi_Process
    {"id": "1JFq6m2-rvSpiGKQsTpr91Hj-RckHpqFfEl_BLkQI_hs", "mode": "named"},  # 유가 인원 정리
]
OUT_PATH = "data/listings.enc.json"
PBKDF2_ITERATIONS = 250_000

INHOUSE_TAB_RE = re.compile(r"in\s*-?\s*house", re.I)

# 헤더 이름은 탭마다 순서도 표기도 다르다. 신 시트는 "TikTok Handle [VN]" 처럼
# [VN]/[KR]/[AUTO] 담당 표시가 붙고, 유가 시트는 탭마다 핸들 컬럼 이름이 제각각이다.
# 위치가 아니라 정규화한 이름으로 찾고, 앞에 있는 alias가 우선한다.
FIELD_ALIASES = {
    "handle": (
        "tiktok handle", "handle", "creator username", "크리에이터명",
        "크리에이터 핸들", "account handle", "크리에이터",
    ),
    "listed_date": ("listed date", "날짜"),
    "link": ("tiktok link", "link"),
    "ox": ("o/x", "o/x & reason"),
    "owner": ("vn owner", "owner", "manager", "담당자"),
    "contacted_date": ("1st email sent", "contacted date"),
    "status": ("status", "reply status", "협업 상태", "확정 여부", "paid /non-paid", "레벨"),
    "product": ("제안 제품", "타겟제품", "협업 제품", "제품"),
    "note": ("note", "reason", "memo", "비고"),
}
# 이메일·전화번호·주소·실명은 의도적으로 제외한다. alias 화이트리스트에 없으므로
# 구조적으로 인덱스에 들어갈 수 없다 — 중복 판정에 필요 없고 유출 시 피해가 가장 크다.


def canon_header(s: str) -> str:
    """'TikTok Handle [VN]' → 'tiktok handle'"""
    s = (s or "").strip().lower()
    s = re.sub(r"\[[^\]]*\]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def normalize_handle(raw: str) -> str:
    """핸들/프로필 URL을 비교용 키로 정규화한다. check.html의 규칙과 반드시 같아야 한다."""
    s = (raw or "").strip()
    if not s:
        return ""
    m = re.search(r"(?:tiktok\.com|instagram\.com)/+@?([^/?#\s]+)", s, re.I)
    if m:
        s = m.group(1)
    s = s.split("?")[0].split("#")[0]
    s = s.strip().lstrip("@").rstrip("/").lower()
    return re.sub(r"[^a-z0-9._]", "", s)


def display_handle(raw: str) -> str:
    s = (raw or "").strip()
    m = re.search(r"(?:tiktok\.com|instagram\.com)/+@?([^/?#\s]+)", s, re.I)
    if m:
        s = m.group(1)
    return s.split("?")[0].strip().lstrip("@").rstrip("/")[:64]


def looks_like_handle(raw: str) -> bool:
    s = (raw or "").strip()
    if not s or s.startswith("#") or " " in s:
        return False
    return len(normalize_handle(s)) >= 3


def build_column_map(header_row: list[str]) -> dict[str, int]:
    """헤더 이름 → 컬럼 인덱스. 같은 이름이 두 번 나오면 처음 것을 쓴다."""
    canon = [canon_header(c) for c in header_row]
    colmap: dict[str, int] = {}
    for field, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            if alias in canon:
                colmap[field] = canon.index(alias)
                break
    return colmap


def find_header_row(rows: list[list[str]], limit: int = 30) -> int | None:
    """핸들 컬럼이 있는 첫 행을 헤더로 본다 (탭마다 상단 설명 블록 높이가 다르다)."""
    for i, row in enumerate(rows[:limit]):
        canon = {canon_header(c) for c in row}
        if canon & set(FIELD_ALIASES["handle"]):
            return i
    return None


def cell(row: list[str], idx: int | None) -> str:
    if idx is None or idx >= len(row):
        return ""
    return (row[idx] or "").strip()


SKIP_HANDLE_VALUES = {"handle", "tiktokhandle", "creatorusername", "크리에이터명"}


def parse_handle_tab(
    rows: list[list[str]], tab_index: int, kind: str, require_date: bool
) -> list[dict]:
    """핸들 컬럼이 있는 탭 하나를 레코드 리스트로.

    require_date=True면 Listed Date가 있는 탭만 리스팅 탭으로 인정한다.
    (영상/스파크애즈 탭에도 Handle 컬럼이 있지만 리스팅 기록이 아니다.)
    유가 시트의 탭들은 이름으로 골라 오므로 날짜를 요구하지 않는다.
    """
    header_idx = find_header_row(rows)
    if header_idx is None:
        return []
    colmap = build_column_map(rows[header_idx])
    if "handle" not in colmap:
        return []
    if require_date and "listed_date" not in colmap:
        return []

    records = []
    for row in rows[header_idx + 1 :]:
        raw = cell(row, colmap["handle"])
        norm = normalize_handle(raw)
        if not norm or norm in SKIP_HANDLE_VALUES:
            continue
        rec = {"h": norm, "d": display_handle(raw), "t": tab_index, "k": kind}

        listed = cell(row, colmap.get("listed_date"))
        if listed:
            rec["l"] = listed[:10]
        owner = cell(row, colmap.get("owner"))
        if owner:
            rec["m"] = owner[:24]
        ox = cell(row, colmap.get("ox")).upper()
        if ox in ("O", "X"):
            rec["o"] = ox
        contacted = cell(row, colmap.get("contacted_date"))
        if contacted:
            rec["c"] = contacted[:10]
        status = cell(row, colmap.get("status"))
        if status and status.upper() not in ("TRUE", "FALSE"):
            rec["s"] = status[:48]
        product = cell(row, colmap.get("product"))
        if product:
            rec["p"] = product[:40]
        note = cell(row, colmap.get("note"))
        if note:
            # "Already collaborating" 같은 메모가 판정에 직접 쓰이므로 짧게 남긴다.
            rec["n"] = note[:80]
        records.append(rec)
    return records


def parse_inhouse_tab(rows: list[list[str]], tab_index: int) -> list[dict]:
    """담당자–핸들 로스터. 헤더가 병합 셀이라 이름으로 못 찾으면 컬럼을 추론한다."""
    header_idx = find_header_row(rows)
    handle_cols: list[int] = []
    manager_col = None
    start = 0

    if header_idx is not None:
        colmap = build_column_map(rows[header_idx])
        if "handle" in colmap:
            handle_cols = [colmap["handle"]]
            manager_col = colmap.get("owner")
            start = header_idx + 1

    if not handle_cols:
        # 핸들처럼 생긴 '서로 다른' 값이 얼마나 많은지로 컬럼을 고른다.
        # 이 탭은 로스터가 좌우로 여러 벌 놓여 있어(예: Inhouse | Pickdi) 여러 컬럼을 받는다.
        width = max((len(r) for r in rows), default=0)
        filled, distinct = [], []
        for ci in range(width):
            vals = [normalize_handle(r[ci]) for r in rows if ci < len(r) and looks_like_handle(r[ci])]
            filled.append(len(vals))
            distinct.append(len(set(vals)))
        if not distinct or max(distinct) < 5:
            return []
        cutoff = max(5, max(distinct) * 0.4)
        # 담당자 컬럼은 같은 이름이 반복되므로 distinct/filled 비율이 낮다.
        handle_cols = [
            ci for ci in range(width)
            if distinct[ci] >= cutoff and distinct[ci] >= 0.8 * filled[ci]
        ]

    records = []
    seen = set()
    for row in rows[start:]:
        for handle_col in handle_cols:
            raw = cell(row, handle_col)
            if not looks_like_handle(raw):
                continue
            norm = normalize_handle(raw)
            if not norm or norm in seen:
                continue
            seen.add(norm)
            if manager_col is not None:
                manager = cell(row, manager_col)[:24]
            else:
                # 핸들 왼쪽에서 가장 가까운 비어있지 않은 셀이 담당자다.
                # 옆에 붙어 있는 다른 로스터의 핸들 컬럼은 건너뛴다.
                manager = ""
                for prev_ci in range(handle_col - 1, -1, -1):
                    if prev_ci in handle_cols:
                        continue
                    val = cell(row, prev_ci)
                    if val and not val.startswith("#"):
                        manager = val[:24]
                        break
            records.append({
                "h": norm, "d": display_handle(raw), "t": tab_index, "k": "inhouse",
                **({"m": manager} if manager else {}),
            })
    return records


def parse_tab(title: str, rows: list[list[str]], tab_index: int, mode: str) -> tuple[str, list[dict]]:
    if mode == "named":
        for pattern, kind in PAID_TAB_PATTERNS:
            if pattern.search(title):
                return kind, parse_handle_tab(rows, tab_index, kind, require_date=False)
        return "", []
    if INHOUSE_TAB_RE.search(title):
        return "inhouse", parse_inhouse_tab(rows, tab_index)
    return "sourcing", parse_handle_tab(rows, tab_index, "sourcing", require_date=True)


def absorb(tabs: list[dict], records: list[dict], sheet_title: str,
           tab_title: str, rows: list[list[str]], mode: str) -> None:
    tab_index = len(tabs)
    kind, parsed = parse_tab(tab_title, rows, tab_index, mode)
    if not parsed:
        # 안내/개요 탭은 여기로 떨어지는 게 정상이다. 다만 빠뜨린 리스팅 탭이
        # 조용히 사라지면 안 되므로 전부 찍어둔다.
        print(f"  · (건너뜀) {tab_title}", file=sys.stderr)
        return
    tabs.append({"n": tab_title, "s": sheet_title, "k": kind, "c": len(parsed)})
    records.extend(parsed)
    print(f"  · {tab_title}: {len(parsed)}건 [{kind}]", file=sys.stderr)


def collect_from_sheets(sources: list[dict]) -> dict:
    import gspread
    from google.oauth2.service_account import Credentials

    sa_file = os.environ.get("SERVICE_ACCOUNT_FILE", "service_account.json")
    creds = Credentials.from_service_account_file(
        sa_file, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )
    client = gspread.authorize(creds)

    tabs: list[dict] = []
    records: list[dict] = []
    for src in sources:
        book = client.open_by_key(src["id"])
        print(f"\n[{book.title}] mode={src['mode']}", file=sys.stderr)
        for ws in book.worksheets():
            absorb(tabs, records, book.title, ws.title, ws.get_all_values(), src["mode"])

    return {"tabs": tabs, "records": records}


def collect_from_fixture(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        fixture = json.load(f)
    tabs: list[dict] = []
    records: list[dict] = []
    for sheet in fixture["sheets"]:
        mode = sheet.get("mode", "auto")
        print(f"\n[{sheet['title']}] mode={mode}", file=sys.stderr)
        for tab in sheet["tabs"]:
            absorb(tabs, records, sheet["title"], tab["name"], tab["rows"], mode)
    return {"tabs": tabs, "records": records}


def encrypt_payload(payload: dict, passcode: str) -> dict:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    packed = gzip.compress(raw, 9)

    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", passcode.encode("utf-8"), salt, PBKDF2_ITERATIONS, dklen=32)
    iv = os.urandom(12)
    ct = AESGCM(key).encrypt(iv, packed, None)

    b64 = lambda b: base64.b64encode(b).decode("ascii")  # noqa: E731
    return {
        "v": 1,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "records": len(payload["records"]),
        "tabs": len(payload["tabs"]),
        # salt/IV가 매번 달라 암호문은 늘 바뀐다. 실제 내용이 바뀌었는지는 이 값으로 판단한다.
        # 평문 페이로드의 해시일 뿐이라 여기서 핸들이 새어나가지는 않는다.
        "content_sha256": hashlib.sha256(raw).hexdigest(),
        "kdf": {"name": "PBKDF2", "hash": "SHA-256",
                "iterations": PBKDF2_ITERATIONS, "salt": b64(salt)},
        "cipher": "AES-GCM",
        "compression": "gzip",
        "iv": b64(iv),
        "ct": b64(ct),
    }


def report(data: dict) -> None:
    """중복 현황을 로그로 남긴다 — 이 수치가 이 도구의 존재 이유다."""
    import collections

    by_kind = collections.Counter(r["k"] for r in data["records"])
    print(f"\n등급별 레코드: {dict(by_kind)}", file=sys.stderr)

    rows = [r for r in data["records"] if r["k"] == "sourcing"]
    counts = collections.Counter(r["h"] for r in rows)
    dup_handles = {h for h, c in counts.items() if c > 1}
    wasted = sum(c - 1 for c in counts.values() if c > 1)
    print(
        f"리스팅 {len(rows)}행 / 고유 {len(counts)} / 중복 핸들 {len(dup_handles)} "
        f"/ 낭비된 행 {wasted} ({wasted / max(len(rows), 1) * 100:.1f}%)",
        file=sys.stderr,
    )

    # 이미 협업 중이거나 제안을 보낸 사람을 또 리스팅한 경우 — 가장 아까운 낭비다.
    for kind, label in (("inhouse", "인하우스"), ("partner", "유가 협업 중"), ("casting", "제안 발송")):
        hits = {r["h"] for r in data["records"] if r["k"] == kind} & set(counts)
        if hits:
            print(f"{label}인데 다시 리스팅된 크리에이터: {len(hits)}명", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", help="시트 대신 읽을 로컬 JSON (자격증명 없이 검증용)")
    ap.add_argument("--out", default=OUT_PATH)
    args = ap.parse_args()

    passcode = os.environ.get("LISTING_PASSCODE", "").strip()
    if not passcode:
        print("LISTING_PASSCODE 환경변수가 비어 있습니다.", file=sys.stderr)
        return 1

    if args.fixture:
        data = collect_from_fixture(args.fixture)
    else:
        data = collect_from_sheets(SOURCES)

    if not data["records"]:
        print("수집된 핸들이 0건입니다. 인덱스를 덮어쓰지 않고 중단합니다.", file=sys.stderr)
        return 1

    report(data)

    envelope = encrypt_payload(data, passcode)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(envelope, f, indent=1)
        f.write("\n")
    print(f"{args.out} 저장 완료 ({os.path.getsize(args.out) / 1024:.0f} KB)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
