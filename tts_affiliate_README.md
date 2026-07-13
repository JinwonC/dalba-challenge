# TTS Affiliate 등록 여부 / GMV 자동 체크

"[미국] 7월 인플루언서" 시트(`gid=88644077`)의 **E열 핸들(53행 이하)** 을 매일 자동으로
조회해서, **W열 = TTS Affiliate 등록 여부**, **X열 = GMV** 를 채웁니다.

## 동작 구조

데이터 소스인 **CRUVA `get_affiliate_data`** 는 Claude 커넥터(MCP)라서 일반 GitHub Action
파이썬 스크립트로는 호출할 수 없습니다. 그래서 자동화는 **매일 예약 실행되는 Claude 세션**이
아래 3단계를 수행합니다.

```
1. 읽기   python tts_affiliate_sync.py read      → E53↓ 유효 핸들 목록 (gviz, 자격증명 불필요)
2. 조회   CRUVA get_affiliate_data(handle)        → 각 핸들의 등록 여부 + GMV (Claude가 호출)
3. 쓰기   python tts_affiliate_sync.py write r.json → W/X 열 기록 (gspread + 서비스 계정)
```

- **W열**: 조회 결과가 있으면 `Y`, 404면 `N`
- **X열**: 등록된 경우 GMV. 기본값은 `med_gmv_revenue`(USD). `gmv_range`(구간 0~N)로 바꿀 수 있음.

## 필요한 1회 설정 (쓰기용 자격증명)

읽기(gviz)와 CRUVA 조회는 추가 설정이 필요 없습니다. **W/X 셀 쓰기에만** Google 서비스 계정이
필요합니다. 대상 시트는 "링크가 있는 누구나 편집 가능"이라 서비스 계정을 시트에 공유할 필요는
없고, **Sheets API가 켜진 서비스 계정 자격증명**만 세션 환경에 있으면 됩니다.

- 이 저장소의 기존 GitHub Action이 쓰는 `SERVICE_ACCOUNT_JSON` 시크릿 값을 그대로 재사용하면 됩니다.
- Claude Code 환경 설정에서 환경변수 `SERVICE_ACCOUNT_JSON` 에 그 JSON 문자열을 넣어 주세요.
  (또는 세션 작업 폴더에 `service_account.json` 파일로 두어도 됩니다.)

## 수동 실행

```bash
pip install gspread google-auth              # 최초 1회
python tts_affiliate_sync.py read            # 핸들 목록 확인
# (Claude가 CRUVA 조회 후 results.json 생성: [{"row":53,"w":"N","x":""}, ...])
python tts_affiliate_sync.py write results.json
```

## 참고

- E열에는 핸들 외에 섹션 라벨("잔여 예산"), 반복 헤더("Name"), 메모가 섞여 있어
  스크립트가 자동으로 걸러냅니다. `handle\n메모` 형태는 첫 줄의 핸들만 사용합니다.
- 현재 E53↓ 유효 핸들 수: 약 326개 → 매일 CRUVA 조회 326건.
  범위를 좁히려면 `tts_affiliate_sync.py` 의 `START_ROW`(또는 END_ROW 추가)를 조정하세요.
- 리전은 US 기준(`get_affiliate_data` 기본값). 다른 리전은 조회 시 `region` 인자로 지정.
