# 새 팀용 사이트 복제 가이드

같은 코드로 Vercel 사이트를 하나 더 만들고, **기존 사이트가 업데이트되면 자동으로 같이 업데이트**되게 하는 방법입니다.

원리: **같은 GitHub 레포·같은 브랜치**를 바라보는 Vercel 프로젝트를 하나 더 만듭니다.
코드는 100% 공유하고, **데이터(히스토리·영상·Drive)와 비밀번호만 환경변수로 분리**합니다.
→ 브랜치에 푸시 한 번이면 두 사이트가 동시에 자동 배포됩니다. 코드 수정은 필요 없습니다.

---

## 1단계 · Upstash Redis 새로 만들기 (히스토리 저장소, 무료)

새 팀은 자기들 히스토리를 따로 쓰므로 DB를 새로 만듭니다.

1. https://upstash.com 로그인 → **Create Database**
2. Name: `dalba-history-<팀이름>` / Type: **Regional** / Region: **us-east-1** / Plan: **Free**
3. 생성 후 **REST API → `.env` 탭**에서 두 값을 복사해 둡니다:
   - `UPSTASH_REDIS_REST_URL`
   - `UPSTASH_REDIS_REST_TOKEN`

---

## 2단계 · Vercel 프로젝트 새로 만들기

1. Vercel → **Add New… → Project**
2. **같은 레포** `JinwonC/dalba-challenge` 선택 → Import
3. 설정:
   - **Project Name**: 예) `dalba-content-analyzer-<팀이름>`
   - **Root Directory**: `content-analyzer`  ← **반드시 지정**
   - Framework Preset: **Other**
4. 아래 3단계 환경변수를 넣고 **Deploy**
5. 배포 후 **Settings → Git → Production Branch** 를
   `claude/determined-fermat-gnbdvg` 로 지정
   (기존 사이트와 같은 브랜치여야 자동 동기화됩니다)

---

## 3단계 · 환경변수 넣기

Settings → Environment Variables. 모두 **Production / Preview / Development** 체크.

### 새로 만들어야 하는 값 (팀별로 분리)

| 변수 | 값 | 비고 |
|---|---|---|
| `UPSTASH_REDIS_REST_URL` | 1단계에서 복사 | 히스토리 저장소 |
| `UPSTASH_REDIS_REST_TOKEN` | 1단계에서 복사 | 히스토리 저장소 |
| `SITE_PASSWORD` | 그 팀이 쓸 비밀번호 | 사이트 접속 암호 |
| `VIDEOS_READ_WRITE_TOKEN` | 새 Blob 스토어 토큰 | 아래 참고 |
| `DRIVE_WEBHOOK_URL` | 4단계에서 생성 | 그 팀 Drive |
| `DRIVE_WEBHOOK_SECRET` | 4단계에서 정한 문자열 | 그 팀 Drive |

**영상 저장소(`VIDEOS_READ_WRITE_TOKEN`)**: Vercel → **Storage → Create Database → Blob**,
이름 `dalba-videos-<팀이름>`, **Public** 으로 생성. 생성 후 해당 스토어를 새 프로젝트에 연결하면
토큰이 자동 주입됩니다. 자동 주입 이름이 `BLOB_READ_WRITE_TOKEN`으로 들어가면,
그 값을 복사해 `VIDEOS_READ_WRITE_TOKEN` 이라는 이름으로 하나 더 추가하세요.

### 기존 값을 그대로 복사하는 것

| 변수 | 비고 |
|---|---|
| `APIFY_TOKEN` | 스크래핑 |
| `GEMINI_API_KEY` | AI 영상분석 |

> ⚠️ **중요 — 사용량은 공유됩니다.**
> 같은 `APIFY_TOKEN` / `GEMINI_API_KEY` 를 쓰면 **두 팀이 같은 월간 한도를 나눠 씁니다.**
> 새 팀이 많이 돌리면 기존 팀까지 한도 초과로 멈춥니다.
> 팀별로 사용량을 분리하려면 **각자 Apify 계정 / Google Cloud 프로젝트에서 키를 따로 발급**해
> 각 사이트에 다른 키를 넣으세요. (권장)

### 넣지 않아도 되는 것

- `BLOB_READ_WRITE_TOKEN` — 기존 사이트의 옛날 히스토리 복구용. 새 사이트엔 불필요.
- `VIDEO_MAX_AGE_DAYS` / `VIDEO_MAX_COUNT` / `VIDEO_MAX_TOTAL_MB` — 기본값(7일 / 40개 / 800MB) 사용.
  다르게 하고 싶을 때만 지정.

---

## 4단계 · 그 팀 Drive 연동 (Apps Script)

리포트를 그 팀 구글 드라이브에 자동 저장하려면, **그 팀 계정으로** 아래를 진행합니다.

1. 저장할 Drive 폴더를 만들고, 주소창에서 폴더 ID를 복사
   `https://drive.google.com/drive/folders/<이 부분이 폴더 ID>`
2. https://script.google.com → **새 프로젝트**
3. 아래 코드를 붙여넣고 맨 위 두 값을 수정:

```javascript
const SECRET = '여기에-비밀문자열';        // DRIVE_WEBHOOK_SECRET 과 동일하게
const FOLDER_ID = '여기에-폴더ID';         // 1번에서 복사한 값

function doPost(e) {
  try {
    const body = JSON.parse(e.postData.contents || '{}');
    if (SECRET && body.secret !== SECRET) {
      return ContentService.createTextOutput(JSON.stringify({ error: 'unauthorized' }))
        .setMimeType(ContentService.MimeType.JSON);
    }
    const doc = DocumentApp.create(body.title || '제목 없음');
    doc.getBody().setText(body.text || '');
    doc.saveAndClose();

    if (FOLDER_ID) {
      const file = DriveApp.getFileById(doc.getId());
      DriveApp.getFolderById(FOLDER_ID).addFile(file);
      DriveApp.getRootFolder().removeFile(file);
    }
    return ContentService.createTextOutput(JSON.stringify({ id: doc.getId(), url: doc.getUrl() }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ error: String(err) }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}
```

4. **배포 → 새 배포 → 유형: 웹 앱**
   - 실행 사용자: **나(Me)**
   - 액세스 권한: **모든 사용자(Anyone)**
   - 배포 후 나오는 **웹 앱 URL**을 복사
5. Vercel 환경변수에 넣기:
   - `DRIVE_WEBHOOK_URL` = 복사한 웹 앱 URL
   - `DRIVE_WEBHOOK_SECRET` = 코드의 `SECRET` 과 동일한 값

> Workspace 계정에서 "모든 사용자" 옵션이 막혀 있으면 관리자 설정이 필요합니다.
> Drive 저장이 필요 없으면 `DRIVE_WEBHOOK_URL` 을 아예 넣지 마세요 — 나머지는 정상 작동합니다.

---

## 5단계 · 확인

1. Deployments 최신 배포가 **Ready + Production** 인지
2. 사이트 접속 → 비밀번호 입력 → 화면이 뜨는지
3. 영상 하나 분석 → 히스토리에 쌓이는지 / Drive에 문서가 생기는지

---

## 자동 업데이트가 되는 원리

두 프로젝트가 **같은 레포의 같은 브랜치**를 보고 있으므로,
그 브랜치에 커밋이 푸시되면 Vercel이 **두 프로젝트를 각각 자동 배포**합니다.

```
git push  →  브랜치 갱신
              ├─→ dalba-content-analyzer         (기존 팀)
              └─→ dalba-content-analyzer-<팀>    (새 팀)
```

- 기능 추가·버그 수정이 **양쪽에 자동 반영**됩니다.
- 데이터(히스토리·영상·Drive)와 비밀번호는 환경변수로 갈려 있어 **서로 섞이지 않습니다.**
- 팀을 더 늘리고 싶으면 1~4단계를 반복하면 됩니다. (개수 제한 없음)
