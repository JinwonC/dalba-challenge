# 크리에이터 리스팅 중복 체크

리스팅하기 전에 **핸들을 먼저 검색해서, 이미 누가 리스팅했으면 건너뛰게** 하는 도구다.

- 페이지: `check.html` → https://jinwonc.github.io/dalba-challenge/check.html
- 데이터: `data/listings.enc.json` (암호화된 인덱스, GitHub Actions가 15분마다 갱신)
- 빌더: `tools/build_listing_index.py`

## 왜 필요한가

인하우스 7명 + 베트남 13명이 각자 탭에 리스팅하는데, 탭을 넘어가는 중복을 아무도 못 잡고 있었다.
시트에 걸린 조건부서식(`RED = the handle is a duplicate within...`)은 **같은 탭 안에서만** 동작한다.

여기에 더해 최근 `d'Alba Onboarding` → `d'Alba_Pickdi_Process`로 옮기면서 담당자들이 일부만 손으로
옮겨 담았기 때문에, 신 시트만 보면 "구 시트엔 이미 있는데 아직 안 옮긴 사람"이 신규로 보인다.
그래서 이 도구는 **두 시트를 함께** 본다.

## 무엇을 읽는가

시트마다 읽는 방식이 다르다. `tools/build_listing_index.py`의 `SOURCES`에 정의돼 있다.

| 시트 | 모드 | 읽는 탭 | 판정 등급 |
|---|---|---|---|
| `d'Alba Onboarding` | auto | `(new) ...` 소싱 탭 | 리스팅 |
| `d'Alba Onboarding` | auto | `d'Alba Inhouse Creator` | 인하우스 |
| `d'Alba_Pickdi_Process` | auto | `firstsprayserum`, `multibalm`, … `07_comfrt` | 리스팅 |
| `유가 인원 정리` | named | `캐스팅` | 제안 발송 |
| `유가 인원 정리` | named | `담당자`, `Flat fee 리스팅`, `PAID 성과 트래킹 (GMV)`, `VIP Creator 협업 정보` | 유가 협업 중 |

**auto 모드**는 탭을 이름이 아니라 **컬럼 구조로** 고른다. 핸들 컬럼과 `Listed Date` 컬럼이 둘 다 있으면
리스팅 탭으로 본다. 그래서

- **새 제품 탭을 추가해도 코드를 고칠 필요가 없다.** 다음 갱신 때 자동으로 잡힌다.
- 안내(`Guide`), 영상성과, 스파크애즈 탭은 자동으로 제외된다. (핸들 컬럼은 있어도 `Listed Date`가 없다)

**named 모드**는 `PAID_TAB_PATTERNS`에 걸리는 탭만 읽는다. `유가 인원 정리`는 26개 탭 중 대부분이
성과·정산·배송용이고 **주소 폼 응답 탭에는 실명·집주소·전화번호가 들어 있어서**, 화이트리스트로만 연다.
탭을 늘리려면 그 목록에 패턴을 추가하면 된다.

헤더 이름은 `TikTok Handle [VN]`, `O/X [KR]`처럼 `[VN]`/`[KR]`/`[AUTO]` 접미사가 붙어도 인식하고,
탭마다 컬럼 순서가 달라도 **위치가 아니라 이름으로** 찾는다. 핸들 컬럼 이름이 시트마다
`Handle` / `TikTok Handle` / `Creator username` / `크리에이터명` / `account handle`로 제각각인 것도
alias 목록으로 흡수한다.

인덱스에 담는 필드는 화이트리스트다 — 핸들, 담당자, 날짜, 상태, 제품, 짧은 메모. **이메일·전화번호·주소·
실명은 alias 목록에 없어서 구조적으로 들어갈 수 없다.**

## 판정 규칙

검색창에 핸들이나 틱톡 링크를 넣으면 넷 중 하나가 나온다.

| 결과 | 뜻 | 할 일 |
|---|---|---|
| 🟣 **이미 유가 협업 중** | 계약·정산 진행 중이거나 담당자가 배정됨 | 절대 리치아웃 금지 |
| 🔵 **이미 협업 중** | 인하우스 로스터에 있음 | 신규 리치아웃 대상 아님 |
| 🟠 **이미 제안을 보냄** | 캐스팅 단계에서 제안이 나감 | 중복 연락 금지 |
| 🔴 **이미 리스팅됨** | 다른 담당자가 이미 리스팅함 (누가·언제·어느 시트/제품인지 표시) | 건너뛴다 |
| 🟡 **비슷한 핸들 있음** | 한두 글자 차이거나 `.`/`_`만 다름 | 확인 후 판단 |
| 🟢 **신규** | 기록에 없음 | 리스팅 진행 |

여러 곳에 걸리면 **가장 강한 신호**를 헤드라인으로 쓰고(유가 협업 > 인하우스 > 제안 발송 > 리스팅),
걸린 곳은 전부 아래에 나열한다.

핸들은 이렇게 정규화해서 비교하므로 형식이 달라도 같은 사람으로 잡힌다.

```
@GiniGlow                                  ┐
https://www.tiktok.com/@giniglow?lang=en   ├─→  giniglow
giniglow/                                  ┘
```

**여러 명 한번에** 탭에서는 핸들을 줄바꿈으로 붙여넣으면 표로 한 번에 판정하고,
`신규만 복사` 버튼으로 걸러진 목록만 가져갈 수 있다. 200건 기준 0.1초.

## 최초 세팅 (1회)

1. **시트를 서비스 계정에 공유**
   `SERVICE_ACCOUNT_JSON` 시크릿 안의 `client_email` 주소에게 세 시트를 **뷰어**로 공유한다.
   ```
   d'Alba Onboarding        (1Bhi85hXhIOHfWu9419drpeOuCOPXRkfMrW-4l_pJRB0)
   d'Alba_Pickdi_Process    (1ZtATip5Ul8cahN80-Oj-TyKb_UkLPBB67RKfnFRumr8)
   유가 인원 정리            (1JFq6m2-rvSpiGKQsTpr91Hj-RckHpqFfEl_BLkQI_hs)
   ```
   `d'Alba Onboarding`과 `유가 인원 정리`는 `dohyeon.kim@dalba.com` 소유라 공유 권한이 필요할 수 있다.

2. **팀 패스코드 시크릿 등록**
   Settings → Secrets and variables → Actions → New repository secret
   - Name: `LISTING_PASSCODE`
   - Secret: 팀에 공유할 패스코드 (예: 12자 이상)

3. **(선택) 읽을 시트·탭을 바꾸려면**
   `tools/build_listing_index.py`의 `SOURCES`(시트)와 `PAID_TAB_PATTERNS`(유가 시트 탭)를 고친다.

4. **GitHub Pages 켜기**
   Settings → Pages → Source: `Deploy from a branch`, Branch: `main` / `/ (root)`

5. **첫 인덱스 만들기**
   Actions → `Creator Listing Index` → Run workflow.
   로그에 탭별 건수와 중복 현황이 찍힌다. 끝나면 `data/listings.enc.json`이 커밋된다.

> 예약 실행(15분 주기)은 **기본 브랜치에서만** 동작한다. 이 브랜치가 `main`에 병합되기 전까지는
> 수동 실행(Run workflow)으로만 갱신된다.

## 팀 공지용 문구

**한국어**
> 리스팅 전에 반드시 여기서 핸들을 먼저 검색하세요 → https://jinwonc.github.io/dalba-challenge/check.html
> 빨간색(이미 리스팅됨)이 나오면 그 크리에이터는 **건너뛰고** 다음 사람으로 넘어가세요.
> 패스코드는 팀 리드에게 문의하세요. 한 번 입력하면 저장됩니다.

**English**
> Before you list anyone, search the handle here first → https://jinwonc.github.io/dalba-challenge/check.html
> If it comes back red (already listed), **skip that creator** and move on to the next one.
> Ask your team lead for the passcode. You only need to enter it once.

**Tiếng Việt**
> Trước khi list bất kỳ ai, hãy tìm handle tại đây → https://jinwonc.github.io/dalba-challenge/check.html
> Nếu kết quả màu đỏ (đã được list), hãy **bỏ qua creator đó** và chuyển sang người tiếp theo.
> Hỏi trưởng nhóm để lấy mã truy cập. Bạn chỉ cần nhập một lần.

## 보안

이 레포는 **공개**다. 크리에이터 핸들 목록을 평문으로 커밋하면 소싱 파이프라인이 그대로 노출되므로,

- 페이로드를 gzip → **AES-GCM 256** 암호화해서 커밋한다. 키는 팀 패스코드에서 **PBKDF2-SHA256 25만 회**로 유도한다.
- 복호화는 **브라우저에서만** 일어난다 (WebCrypto). 패스코드는 서버로 나가지 않는다.
- **이메일과 전화번호는 인덱스에 아예 담지 않는다.** 중복 판정에 필요 없다.
- 페이지에 `noindex, nofollow`를 걸어 검색엔진에 잡히지 않게 했다.

패스코드가 유출되면 `LISTING_PASSCODE` 시크릿을 바꾸고 워크플로를 한 번 돌리면 된다.
기존 링크를 아는 사람도 새 패스코드 없이는 못 연다.

## 한계

- **조회 전용이다.** 두 사람이 *동시에* 같은 신규 크리에이터를 리스팅하는 경합은 막지 못한다.
  선점 등록(웹에서 바로 "내가 찜")을 붙이면 그것까지 막을 수 있다.
- 인덱스는 최대 15분 지연된다. 방금 다른 사람이 넣은 건은 다음 갱신 후에 잡힌다.
- **블랙리스트 탭은 읽지 않는다.** 지정된 5개 탭만 보도록 범위를 정했기 때문이다.
  넣으려면 `PAID_TAB_PATTERNS`에 `(re.compile(r"블랙리스트"), "blocked")` 한 줄을 추가하고
  판정 등급을 하나 늘리면 된다.
- 구 시트 `(new)` 탭에는 담당자 컬럼이 없어서 **탭 이름**으로 표시된다.
  신 시트는 `VN Owner`, 유가 시트는 `담당자` 컬럼이 있어 담당자 이름이 정확히 나온다.
  다만 유가 시트는 한국어 이름(김도현), 앞의 두 시트는 영문 이름(Delilah, Linh)이라 표기가 섞인다.
  그래서 결과에 **출처 시트를 함께** 표시한다.

## 로컬에서 확인하기

자격증명 없이 파서를 검증할 수 있다.

```bash
pip install cryptography
LISTING_PASSCODE=test python tools/build_listing_index.py \
  --fixture tools/fixtures/sample.json --out /tmp/test.enc.json
```

픽스처에는 실제 시트의 까다로운 구조가 들어 있다 — 탭마다 다른 컬럼 순서, 중복 헤더(`Note`, `Status`),
`[VN]`/`[KR]` 접미사, URL·`@`·대소문자가 섞인 핸들, 건너뛰어야 하는 안내/영상 탭.
