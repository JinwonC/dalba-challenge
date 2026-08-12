# 크리에이터 리스팅 중복 체크

리스팅하기 전에 **핸들을 먼저 검색해서, 이미 누가 리스팅했으면 건너뛰게** 하는 도구다.

- 페이지: `check.html` → https://jinwonc.github.io/dalba-check/check.html
- 데이터: `data/listings.enc.json` (암호화된 인덱스, GitHub Actions가 15분마다 갱신)
- 빌더: `tools/build_listing_index.py`

## 무엇을 읽는가

**`d'Alba_Pickdi_Process` 시트의 `duplicate` 탭 하나만** 읽는다. 이 탭에 두 개의 리스팅이 나란히 있다.

| 열 | 내용 | 판정 등급 |
|---|---|---|
| A~D | 베트남 팀 리스팅 — A 제품 탭, B 담당자, C 리스팅일, D 핸들. 제품 탭 7개를 `VSTACK`으로 쌓은 통합 뷰 | 🔴 리스팅 |
| P~S | 인하우스 캐스팅 — P 날짜, Q 담당자, R 제안 제품, S 핸들 (T·U 상태) | 🔵 인하우스 |
| W | 유가 paid 핸들 | 🔵 인하우스 |

**중복 표시가 필요한 건 이 두 리스팅 사이**(그리고 베트남 팀 내부의 담당자 간)이고, 색으로 갈린다 —
베트남 팀 리스팅과 겹치면 🔴, 인하우스 리스팅(S·W열)과 겹치면 🔵.

시트의 조건부서식도 같은 duplicate 탭을 참조하므로 **웹 페이지와 시트가 정확히 같은 데이터를 본다.**
헤더 행이 없어 열 번호로 읽는다. 열 위치가 밀리면 조용히 망가지므로, 담당자 열(B·Q)이 절반 미만으로만
채워지면 빌드 로그에 경고가 뜬다.

인덱스에 담는 필드는 화이트리스트다 — 핸들, 담당자, 날짜, 상태, 제품. **이메일·전화번호·주소·실명은
구조적으로 들어갈 수 없다.**

## 판정 규칙

검색창에 핸들이나 틱톡 링크를 넣으면 이 중 하나가 나온다.

| 결과 | 뜻 | 할 일 |
|---|---|---|
| 🔵 **이미 협업 중** | 인하우스 리스팅(S·W열)에 있음 | 신규 리치아웃 대상 아님 |
| 🔴 **이미 리스팅됨** | 다른 담당자가 이미 리스팅함 (누가·언제·어느 제품인지 표시) | 건너뛴다 |
| 🟡 **비슷한 핸들 있음** | 한두 글자 차이거나 `.`/`_`만 다름 | 확인 후 판단 |
| 🟢 **신규** | 기록에 없음 | 리스팅 진행 |

두 리스팅에 모두 걸리면 **인하우스 쪽을 헤드라인**으로 쓰고, 걸린 곳은 전부 아래에 나열한다.

우측 상단에서 **본인 이름을 고르면** 판정이 하나 더 갈린다. 리스팅한 사람이 본인뿐이면
🔴 대신 ⚪ **"본인이 이미 리스팅한 크리에이터"** 로 표시된다 — 본인 기록은 중복이 아니기 때문이다.
시트 조건부서식의 `"<>"&$A3` 규칙과 같은 판단이다.

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
   `SERVICE_ACCOUNT_JSON` 시크릿 안의 `client_email` 주소에게 아래 시트를 **뷰어**로 공유한다.
   ```
   d'Alba_Pickdi_Process    (1ZtATip5Ul8cahN80-Oj-TyKb_UkLPBB67RKfnFRumr8)
   ```

2. **팀 패스코드 시크릿 등록**
   Settings → Secrets and variables → Actions → New repository secret
   - Name: `LISTING_PASSCODE`
   - Secret: 팀에 공유할 패스코드 (예: 12자 이상)

3. **GitHub Pages 켜기**
   Settings → Pages → Source: `Deploy from a branch`, Branch: `main` / `/ (root)`

4. **첫 인덱스 만들기**
   Actions → `Creator Listing Index` → Run workflow.
   로그에 리스팅별 건수와 중복 현황이 찍힌다. 끝나면 `data/listings.enc.json`이 커밋된다.

> 예약 실행(15분 주기)은 **기본 브랜치에서만** 동작한다. 시크릿이 등록되기 전에는
> 실행이 조용히 건너뛴다(실패 알림이 쌓이지 않도록).

## 팀 공지용 문구

**한국어**
> 리스팅 전에 반드시 여기서 핸들을 먼저 검색하세요 → https://jinwonc.github.io/dalba-check/check.html
> 빨간색(이미 리스팅됨)이나 파란색(인하우스 협업 중)이 나오면 그 크리에이터는 **건너뛰고** 다음 사람으로 넘어가세요.
> 패스코드는 팀 리드에게 문의하세요. 한 번 입력하면 저장됩니다.

**English**
> Before you list anyone, search the handle here first → https://jinwonc.github.io/dalba-check/check.html
> If it comes back red (already listed) or blue (in-house partner), **skip that creator** and move on to the next one.
> Ask your team lead for the passcode. You only need to enter it once.

**Tiếng Việt**
> Trước khi list bất kỳ ai, hãy tìm handle tại đây → https://jinwonc.github.io/dalba-check/check.html
> Nếu kết quả màu đỏ (đã được list) hoặc xanh dương (đối tác in-house), hãy **bỏ qua creator đó** và chuyển sang người tiếp theo.
> Hỏi trưởng nhóm để lấy mã truy cập. Bạn chỉ cần nhập một lần.

## 보안

이 레포는 **공개**다. 크리에이터 핸들 목록을 평문으로 커밋하면 소싱 파이프라인이 그대로 노출되므로,

- 페이로드를 gzip → **AES-GCM 256** 암호화해서 커밋한다. 키는 팀 패스코드에서 **PBKDF2-SHA256 25만 회**로 유도한다.
- 복호화는 **브라우저에서만** 일어난다. 패스코드는 서버로 나가지 않는다.
  (HTTPS 페이지에서는 WebCrypto, HTTP로 열린 경우엔 동일한 결과를 내는 내장 JS 구현을 쓴다.)
- **이메일과 전화번호는 인덱스에 아예 담지 않는다.** 중복 판정에 필요 없다.
- 페이지에 `noindex, nofollow`를 걸어 검색엔진에 잡히지 않게 했다.

패스코드가 유출되면 `LISTING_PASSCODE` 시크릿을 바꾸고 워크플로를 한 번 돌리면 된다.
기존 링크를 아는 사람도 새 패스코드 없이는 못 연다.

## 한계

- **조회 전용이다.** 두 사람이 *동시에* 같은 신규 크리에이터를 리스팅하는 경합은 웹이 아니라
  시트의 조건부서식이 실시간으로 잡는다. 웹 인덱스는 최대 15분 지연된다.
- W열(유가 paid)은 핸들만 있어서 담당자·날짜 없이 "in-house"로만 표시된다.

## 로컬에서 확인하기

자격증명 없이 파서를 검증할 수 있다.

```bash
pip install cryptography
LISTING_PASSCODE=test python tools/build_listing_index.py \
  --fixture tools/fixtures/sample.json --out /tmp/test.enc.json
```

픽스처에는 duplicate 탭의 구조가 들어 있다 — 두 리스팅이 나란히 놓인 행, 담당자 간 중복,
인하우스·유가 paid와 겹치는 핸들, URL·`@`·대소문자가 섞인 표기.
