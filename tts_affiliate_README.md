# TTS Affiliate 등록 여부 / GMV 자동 체크

"[미국] 7월 인플루언서" 시트(`gid=88644077`)의 **E열 크리에이터 핸들**을 매일 확인해서,
**등록된(=TikTok Shop 어필리에이트) 핸들만** W열=`Y`, X열=`GMV(med_gmv_revenue)`로 채운다.

## 핵심 원칙 (안전)

- **등록된 것만 표기**한다. 미등록(404)·핸들 아닌 셀은 **손대지 않는다**(빈칸 유지).
- **절대 행번호를 쓰지 않는다.** 시트는 실시간 편집돼 행이 계속 이동하므로,
  쓰기 직전에 시트를 다시 읽어 **핸들로 현재 행을 찾아** 기록한다(`_handle_row_map`).
- **이미 채운 셀(W에 값 있음)은 다시 건드리지 않는다.** 매일 **비어 있는 핸들만** 새로 조회.
  → 오늘 미등록이어도 나중에 등록되면 다음 실행에서 자동으로 잡힌다.
- 시트 읽기는 반드시 **인증(gspread)** 으로. (gviz 공개읽기는 캐시로 행/목록이 어긋나 신뢰 불가.)

## 왜 GitHub Action + Claude 세션 조합인가

- 등록여부/GMV 데이터원인 **CRUVA `get_affiliate_data`는 Claude 커넥터(MCP)** 라 Claude 세션에서만 호출된다.
- 시트 인증 읽기/쓰기는 **서비스 계정이 필요**하고, 그 자격증명은 **GitHub Secret `SERVICE_ACCOUNT_JSON`**
  에 있어 GitHub Action만 읽을 수 있다. (이 시트는 링크공개편집이라 시트 공유는 불필요.)
- 그래서 역할을 나눈다: **인증 시트 I/O = Action**, **CRUVA 조회 = Claude 세션**.

## 워크플로우 / 스크립트

- `tts_affiliate_sync.py`
  - `pending` : 인증 읽기 → W 비어있는 유효 핸들만 유니크 JSON 출력(로그의 `PENDING_JSON_START/END` 사이)
  - `write results.json` : `[{"handle","w","x"}]`를 **핸들 매칭**으로 W/X에 기록(등록=Y만 넘김)
  - `dump` : 진단용 E/W/X 덤프
- `.github/workflows/tts_affiliate_pending.yml` : `PENDING_TRIGGER` 푸시 시 `pending` 실행
- `.github/workflows/tts_affiliate_write.yml`   : `results.json` 푸시 시 `write` 실행
- `.github/workflows/tts_affiliate_dump.yml`    : `DUMP_TRIGGER` 푸시 시 `dump`(디버그)

## 매일 자동 흐름 (스케줄 Claude 세션이 수행)

1. 브랜치 체크아웃. CRUVA 도구 사용 가능한지 확인(없으면 중단·보고).
2. `PENDING_TRIGGER` 갱신 푸시 → `pending` 워크플로우 실행 → 로그에서 미기입 핸들 목록 추출.
3. 각 핸들을 CRUVA `get_affiliate_data`(region us)로 조회. 등록된 것만
   `{"handle","w":"Y","x":"$"+med_gmv_revenue}` 로 수집(404는 제외).
4. `results.json` 푸시 → `write` 워크플로우가 핸들 매칭으로 W/X 기록.
5. 신규 등록 수 / 확인 수 / 미등록 수 보고.

## 1차 반영 결과(수동)

- 대상 유효 핸들(미기입) 약 408 → **등록 173명**을 Y+GMV로 기록, 미발견 0.
- 상위 GMV 예: officialkatjames $137,806 · makeupd0ll $59,176 · camillecowher $27,785 · byvickyalvarez $27,453 · arshiamoorjani $17,290.
