#!/usr/bin/env python3
"""d'Alba_Pickdi_Process 시트의 duplicate 탭 하나로 크리에이터 중복체크 인덱스를 만든다.

duplicate 탭에 두 개의 리스팅이 나란히 있다.
  - A~D열   : 베트남 팀 리스팅 (A 제품 탭, B 담당자, C 리스팅일, D 핸들)
              — 제품 탭 7개를 VSTACK으로 쌓은 통합 뷰
  - P~W열   : 인하우스 리스팅 (P 날짜, Q 담당자, R 제안 제품, S 핸들 / W 유가 paid 핸들)
중복 표시가 필요한 건 이 두 리스팅 사이(그리고 베트남 팀 내부의 담당자 간)다.

레포가 public이므로 크리에이터 핸들은 평문으로 커밋하지 않는다.
페이로드를 gzip → AES-GCM 암호화해 data/listings.enc.json 으로 저장하고,
브라우저에서 팀 패스코드로만 복호화한다. 이메일은 아예 담지 않는다.

    python tools/build_listing_index.py
    python tools/build_listing_index.py --fixture tools/fixtures/sample.json   # 자격증명 없이 검증

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

SHEET_ID = "1ZtATip5Ul8cahN80-Oj-TyKb_UkLPBB67RKfnFRumr8"  # d'Alba_Pickdi_Process
DUPLICATE_TAB_RE = re.compile(r"^\s*duplicate\s*$", re.I)
OUT_PATH = "data/listings.enc.json"
PBKDF2_ITERATIONS = 250_000

# duplicate 탭은 헤더 행이 없고 열 위치가 고정이라 이름이 아니라 열 번호로 읽는다.
VN_COLS = {"product": 0, "owner": 1, "listed": 2, "handle": 3}          # A~D
IH_COLS = {"date": 15, "owner": 16, "product": 17, "handle": 18,        # P~S
           "status": 19, "collab": 20}                                  # T, U
PAID_COL = 22                                                           # W  유가 paid


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


SKIP_HANDLE_VALUES = {"handle", "tiktokhandle"}


def cell(row: list[str], idx: int) -> str:
    if idx >= len(row):
        return ""
    return (row[idx] or "").strip()


def parse_duplicate_tab(rows: list[list[str]], sheet_title: str) -> tuple[list[dict], list[dict]]:
    """duplicate 탭 → (탭 메타 3개, 레코드). 잘못된 열을 읽고 있으면 조용히 넘어가지 않는다."""
    vn, inhouse, paid = [], [], []
    seen_ih, seen_paid = set(), set()

    for row in rows:
        # 베트남 팀 리스팅: A열에 제품 탭 이름이 있고 D열이 핸들처럼 보이는 행만 데이터로 본다.
        product_tab = cell(row, VN_COLS["product"])
        raw = cell(row, VN_COLS["handle"])
        if product_tab and looks_like_handle(raw):
            norm = normalize_handle(raw)
            if norm and norm not in SKIP_HANDLE_VALUES:
                rec = {"h": norm, "d": display_handle(raw), "t": 0, "k": "sourcing",
                       "p": product_tab[:40]}
                if (owner := cell(row, VN_COLS["owner"])):
                    rec["m"] = owner[:24]
                if (listed := cell(row, VN_COLS["listed"])):
                    rec["l"] = listed[:10]
                vn.append(rec)

        # 인하우스 캐스팅 (S열). 같은 핸들이 여러 행에 반복되므로 첫 행만 담는다.
        raw = cell(row, IH_COLS["handle"])
        if looks_like_handle(raw):
            norm = normalize_handle(raw)
            if norm and norm not in SKIP_HANDLE_VALUES and norm not in seen_ih:
                seen_ih.add(norm)
                rec = {"h": norm, "d": display_handle(raw), "t": 1, "k": "inhouse"}
                if (owner := cell(row, IH_COLS["owner"])):
                    rec["m"] = owner[:24]
                if (date := cell(row, IH_COLS["date"])):
                    rec["l"] = date[:10]
                if (product := cell(row, IH_COLS["product"])):
                    rec["p"] = product[:40]
                status = cell(row, IH_COLS["collab"]) or cell(row, IH_COLS["status"])
                if status:
                    rec["s"] = status[:48]
                inhouse.append(rec)

        # 유가 paid (W열). 메타 컬럼 없이 핸들만 있다.
        raw = cell(row, PAID_COL)
        if looks_like_handle(raw):
            norm = normalize_handle(raw)
            if norm and norm not in SKIP_HANDLE_VALUES and norm not in seen_paid:
                seen_paid.add(norm)
                paid.append({"h": norm, "d": display_handle(raw), "t": 2, "k": "inhouse"})

    # 열이 밀리면 담당자 자리에 날짜가 들어오는 식으로 조용히 망가진다.
    # 담당자가 거의 안 채워지면 위치가 틀어졌다고 보고 알린다.
    for label, records in (("VN(B열)", vn), ("인하우스(Q열)", inhouse)):
        if records:
            with_owner = sum(1 for r in records if r.get("m"))
            if with_owner < len(records) * 0.5:
                print(
                    f"  ⚠ {label} 담당자가 {with_owner}/{len(records)}행만 채워짐 — "
                    "열 위치가 바뀌었는지 확인 필요",
                    file=sys.stderr,
                )

    tabs = [
        {"n": "VN 리스팅", "s": sheet_title, "k": "sourcing", "c": len(vn)},
        {"n": "인하우스 캐스팅", "s": sheet_title, "k": "inhouse", "c": len(inhouse)},
        {"n": "유가 paid", "s": sheet_title, "k": "inhouse", "c": len(paid)},
    ]
    records = vn + inhouse + paid
    for tab in tabs:
        print(f"  · {tab['n']}: {tab['c']}건 [{tab['k']}]", file=sys.stderr)
    return tabs, records


def collect_from_sheets() -> dict:
    import gspread
    from google.oauth2.service_account import Credentials

    sa_file = os.environ.get("SERVICE_ACCOUNT_FILE", "service_account.json")
    creds = Credentials.from_service_account_file(
        sa_file, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )
    client = gspread.authorize(creds)

    book = client.open_by_key(SHEET_ID)
    print(f"\n[{book.title}]", file=sys.stderr)
    for ws in book.worksheets():
        if DUPLICATE_TAB_RE.match(ws.title):
            tabs, records = parse_duplicate_tab(ws.get_all_values(), book.title)
            return {"tabs": tabs, "records": records}
    raise SystemExit("duplicate 탭을 찾지 못했습니다.")


def collect_from_fixture(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        fixture = json.load(f)
    for sheet in fixture["sheets"]:
        for tab in sheet["tabs"]:
            if DUPLICATE_TAB_RE.match(tab["name"]):
                print(f"\n[{sheet['title']}] (fixture)", file=sys.stderr)
                tabs, records = parse_duplicate_tab(tab["rows"], sheet["title"])
                return {"tabs": tabs, "records": records}
    raise SystemExit("fixture에서 duplicate 탭을 찾지 못했습니다.")


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

    vn = [r for r in data["records"] if r["k"] == "sourcing"]
    ih = {r["h"] for r in data["records"] if r["k"] == "inhouse"}

    counts = collections.Counter(r["h"] for r in vn)
    owners = collections.defaultdict(set)
    for r in vn:
        owners[r["h"]].add(r.get("m", ""))
    cross_vn = sum(1 for h, c in counts.items() if c > 1 and len(owners[h]) > 1)
    print(
        f"\nVN 리스팅 {len(vn)}행 / 고유 {len(counts)} / "
        f"담당자 간 중복 핸들 {cross_vn}",
        file=sys.stderr,
    )
    overlap = [h for h in counts if h in ih]
    print(f"인하우스 리스팅과 겹치는 핸들 {len(overlap)}", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", help="시트 대신 읽을 로컬 JSON (자격증명 없이 검증용)")
    ap.add_argument("--out", default=OUT_PATH)
    args = ap.parse_args()

    passcode = os.environ.get("LISTING_PASSCODE", "").strip()
    if not passcode:
        print("LISTING_PASSCODE 환경변수가 비어 있습니다.", file=sys.stderr)
        return 1

    data = collect_from_fixture(args.fixture) if args.fixture else collect_from_sheets()

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
