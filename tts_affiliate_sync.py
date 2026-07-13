"""
TTS Affiliate 등록 여부 / GMV → Google Sheets 동기화 헬퍼

대상 시트: "[미국] 7월 인플루언서" 탭 (gid=88644077)
  - E열: 크리에이터 핸들 (53행 이하)
  - W열: TTS Affiliate 등록 여부
  - X열: 등록된 경우 GMV

이 스크립트는 시트 I/O만 담당합니다. 실제 등록 여부/GMV 데이터는
CRUVA(get_affiliate_data)에서 가져오며, 그 호출은 Claude 세션이 수행합니다.

  1) read  : E53 이하의 유효 핸들을 (행번호, 핸들) JSON으로 출력  (자격증명 불필요, gviz 사용)
  2) write : {행: (W값, X값)} 결과를 W/X 열에 기록            (서비스 계정 필요, gspread 사용)

서비스 계정 자격증명은 다음 중 하나로 제공합니다:
  - 환경변수 SERVICE_ACCOUNT_JSON (JSON 문자열)
  - 파일 service_account.json

대상 시트는 "링크가 있는 누구나 편집 가능"으로 설정되어 있어, 서비스 계정을
시트에 따로 공유하지 않아도 (Sheets API가 활성화된) 아무 서비스 계정으로 기록됩니다.
"""

import json
import os
import re
import sys
import urllib.parse
import urllib.request

SPREADSHEET_ID = "1pB_lJC41rLGfOFmAMgeU6INywUX5kHw_h5ippFR79kk"
GID = 88644077                      # "[미국] 7월 인플루언서" 탭
START_ROW = 53                     # 이 행부터 핸들 스캔
HANDLE_COL = "E"
STATUS_COL = "W"                   # 등록 여부
GMV_COL = "X"                      # GMV

# 핸들이 아닌 셀(섹션 라벨/헤더)을 걸러내기 위한 규칙
_HANDLE_RE = re.compile(r"^[A-Za-z0-9._]+$")
_SKIP_TOKENS = {"name"}            # 반복되는 컬럼 헤더 "Name"


def _clean_handle(cell_value):
    """셀 값에서 유효한 핸들만 추출. 아니면 None.

    - 'handle\\n메모' 형태는 첫 줄만 취함
    - 공백/한글이 섞인 섹션 라벨('잔여 예산' 등)은 제외
    - 반복 헤더 'Name' 제외
    """
    if cell_value is None:
        return None
    first = str(cell_value).split("\n")[0].strip()
    if not first:
        return None
    if first.lower() in _SKIP_TOKENS:
        return None
    if not _HANDLE_RE.match(first):
        return None
    return first


def read_handles():
    """gviz로 E열 전체를 읽어 (행번호, 핸들) 목록 반환. 자격증명 불필요."""
    tq = urllib.parse.quote("select E")
    url = (
        f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq"
        f"?gid={GID}&headers=0&tq={tq}"
    )
    with urllib.request.urlopen(url, timeout=30) as resp:
        raw = resp.read().decode("utf-8")
    payload = re.search(r"setResponse\((.*)\);?\s*$", raw, re.S).group(1)
    rows = json.loads(payload)["table"]["rows"]

    out = []
    for idx, r in enumerate(rows):
        rownum = idx + 1          # headers=0 → 스프레드시트 행번호 == idx+1
        if rownum < START_ROW:
            continue
        cells = r.get("c", [])
        e = cells[0].get("v") if cells and cells[0] else None
        handle = _clean_handle(e)
        if handle:
            out.append({"row": rownum, "handle": handle})
    return out


def _gspread_worksheet():
    import gspread
    from google.oauth2.service_account import Credentials

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    if os.environ.get("SERVICE_ACCOUNT_JSON"):
        info = json.loads(os.environ["SERVICE_ACCOUNT_JSON"])
        creds = Credentials.from_service_account_info(info, scopes=scopes)
    elif os.path.exists("service_account.json"):
        creds = Credentials.from_service_account_file("service_account.json", scopes=scopes)
    else:
        raise SystemExit(
            "서비스 계정 자격증명이 없습니다. 환경변수 SERVICE_ACCOUNT_JSON 또는 "
            "service_account.json 파일을 제공하세요."
        )
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SPREADSHEET_ID)
    for ws in sh.worksheets():
        if ws.id == GID:
            return ws
    raise SystemExit(f"gid={GID} 워크시트를 찾지 못했습니다.")


def write_results(results):
    """results: [{'row': int, 'w': str, 'x': str}, ...] 를 W/X 열에 기록."""
    ws = _gspread_worksheet()
    updates = []
    for item in results:
        row = item["row"]
        updates.append({"range": f"{STATUS_COL}{row}", "values": [[item.get("w", "")]]})
        updates.append({"range": f"{GMV_COL}{row}", "values": [[item.get("x", "")]]})
    if not updates:
        print("기록할 항목이 없습니다.")
        return
    ws.batch_update(updates, value_input_option="USER_ENTERED")
    print(f"{len(results)}개 행의 {STATUS_COL}/{GMV_COL} 열을 업데이트했습니다.")


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("read", "write"):
        print("사용법: python tts_affiliate_sync.py [read | write <results.json>]")
        raise SystemExit(2)

    if sys.argv[1] == "read":
        handles = read_handles()
        print(json.dumps(handles, ensure_ascii=False, indent=2))
        return

    # write
    if len(sys.argv) < 3:
        raise SystemExit("write 모드는 결과 JSON 경로가 필요합니다.")
    with open(sys.argv[2], encoding="utf-8") as f:
        results = json.load(f)
    write_results(results)


if __name__ == "__main__":
    main()
