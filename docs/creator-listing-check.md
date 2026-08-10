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

| 시트 | 읽는 탭 | 의미 |
|---|---|---|
| `d'Alba Onboarding` | `(new) ...` 소싱 탭 | 지금까지의 리스팅 이력 |
| `d'Alba Onboarding` | `d'Alba Inhouse Creator` | 이미 협업 중인 크리에이터 |
| `d'Alba_Pickdi_Process` | `firstsprayserum`, `multibalm`, … `07_comfrt` | 현재 진행중인 제품별 리스팅 |

탭은 **이름이 아니라 컬럼 구조로** 고른다. `TikTok Handle`(또는 `Handle`) 컬럼과 `Listed Date`
컬럼이 둘 다 있으면 리스팅 탭으로 본다. 그래서

- **새 제품 탭을 추가해도 코드를 고칠 필요가 없다.** 다음 갱신 때 자동으로 잡힌다.
- 안내(`Guide`), 영상성과, 스파크애즈 탭은 자동으로 제외된다. (핸들 컬럼은 있어도 `Listed Date`가 없다)

헤더 이름은 `TikTok Handle [VN]`, `O/X [KR]`처럼 `[VN]`/`[KR]`/`[AUTO]` 접미사가 붙어도 인식하고,
탭마다 컬럼 순서가 달라도 **위치가 아니라 이름으로** 찾으므로 상관없다.

## 판정 규칙

검색창에 핸들이나 틱톡 링크를 넣으면 넷 중 하나가 나온다.

| 결과 | 뜻 | 할 일 |
|---|---|---|
| 🔴 **이미 리스팅됨** | 다른 담당자가 이미 리스팅함 (누가·언제·어느 시트/제품인지 표시) | 건너뛴다 |
| 🔵 **이미 협업 중** | 인하우스 로스터에 있음 | 신규 리치아웃 대상 아님 |
| 🟡 **비슷한 핸들 있음** | 한두 글자 차이거나 `.`/`_`만 다름 | 확인 후 판단 |
| 🟢 **신규** | 기록에 없음 | 리스팅 진행 |

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
   `SERVICE_ACCOUNT_JSON` 시크릿 안의 `client_email` 주소에게 두 시트를 **뷰어**로 공유한다.
   ```
   d'Alba Onboarding        (1Bhi85hXhIOHfWu9419drpeOuCOPXRkfMrW-4l_pJRB0)
   d'Alba_Pickdi_Process    (1ZtATip5Ul8cahN80-Oj-TyKb_UkLPBB67RKfnFRumr8)
   ```
   `d'Alba Onboarding`은 `dohyeon.kim@dalba.com` 소유라 공유 권한이 필요할 수 있다.

2. **팀 패스코드 시크릿 등록**
   Settings → Secrets and variables → Actions → New repository secret
   - Name: `LISTING_PASSCODE`
   - Secret: 팀에 공유할 패스코드 (예: 12자 이상)

3. **(선택) 시트 ID를 바꾸려면**
   Settings → Secrets and variables → Actions → **Variables** 탭
   - Name: `LISTING_SHEET_IDS`
   - Value: 쉼표로 구분한 시트 ID. 비워두면 위 두 개가 기본값.

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
- 구 시트 `(new)` 탭에는 담당자 컬럼이 없어서 **탭 이름**으로 표시된다.
  신 시트는 `VN Owner` 컬럼이 있어 담당자 이름이 정확히 나온다.

## 로컬에서 확인하기

자격증명 없이 파서를 검증할 수 있다.

```bash
pip install cryptography
LISTING_PASSCODE=test python tools/build_listing_index.py \
  --fixture tools/fixtures/sample.json --out /tmp/test.enc.json
```

픽스처에는 실제 시트의 까다로운 구조가 들어 있다 — 탭마다 다른 컬럼 순서, 중복 헤더(`Note`, `Status`),
`[VN]`/`[KR]` 접미사, URL·`@`·대소문자가 섞인 핸들, 건너뛰어야 하는 안내/영상 탭.
