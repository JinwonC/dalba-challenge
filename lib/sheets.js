// Google Sheets 접근 (google-auth-library + REST fetch, 경량)
import { GoogleAuth } from 'google-auth-library';

const SHEET_ID = process.env.SHEET_ID || '1_qkd6LZ1wFoihhJSuYdabQ4iRbx-jsFYVxeGIoEb-_g';
// 영상 데이터 원본 탭. 헤더가 1행이 아니라 2행에 있음(1행은 배너), 데이터는 3행부터.
const TAB_NAME = process.env.SHEET_TAB || 'pickdi video list';
const HEADER_ROW = parseInt(process.env.SHEET_HEADER_ROW || '2', 10);
// 상/중/하 평가 + 특이사항은 별도 탭에 저장(매일 자동적재가 원본을 덮어써도 안전).
const REVIEW_TAB = process.env.REVIEW_TAB || '영상리뷰';
const REVIEW_HEADER = ['id', '평가', '특이사항', 'updated'];

const enc = encodeURIComponent;
const q = (name) => "'" + String(name).replace(/'/g, "''") + "'";

async function token() {
  const raw = process.env.GOOGLE_SERVICE_ACCOUNT_JSON;
  if (!raw) throw new Error('GOOGLE_SERVICE_ACCOUNT_JSON env 없음');
  const creds = JSON.parse(raw);
  const auth = new GoogleAuth({
    credentials: {
      client_email: creds.client_email,
      private_key: (creds.private_key || '').replace(/\\n/g, '\n'),
    },
    scopes: ['https://www.googleapis.com/auth/spreadsheets'],
  });
  const client = await auth.getClient();
  const t = await client.getAccessToken();
  return typeof t === 'string' ? t : t.token;
}

async function api(path, opts = {}) {
  const tk = await token();
  const res = await fetch(`https://sheets.googleapis.com/v4/spreadsheets/${SHEET_ID}${path}`, {
    ...opts,
    headers: { Authorization: `Bearer ${tk}`, 'Content-Type': 'application/json', ...(opts.headers || {}) },
  });
  const j = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(`Sheets ${res.status}: ${JSON.stringify(j).slice(0, 300)}`);
  return j;
}

export function colLetter(i) {
  let n = i + 1, s = '';
  while (n) { const r = (n - 1) % 26; s = String.fromCharCode(65 + r) + s; n = Math.floor((n - 1) / 26); }
  return s;
}

// 원본 영상 탭을 읽어 { header, rows } 반환 (header=HEADER_ROW행, rows=그 아래 데이터행)
export async function readVideoTable() {
  const j = await api(`/values/${enc(q(TAB_NAME))}`);
  const all = j.values || [];
  const header = all[HEADER_ROW - 1] || [];
  const rows = all.slice(HEADER_ROW);
  return { header, rows };
}

// ── 별도 리뷰 탭 ────────────────────────────────────────────────
// 리뷰 탭 A:D 읽기. 탭이 없으면(파싱 400) 생성 후 헤더만 있는 상태로 반환.
async function readReviewRows() {
  try {
    const j = await api(`/values/${enc(q(REVIEW_TAB))}!A:D`);
    return j.values || [REVIEW_HEADER];
  } catch (e) {
    if (/Unable to parse range/i.test(String(e.message || ''))) {
      await batchUpdate({ requests: [{ addSheet: { properties: { title: REVIEW_TAB } } }] });
      await updateRange(`${q(REVIEW_TAB)}!A1:${colLetter(REVIEW_HEADER.length - 1)}1`, [REVIEW_HEADER]);
      return [REVIEW_HEADER];
    }
    throw e;
  }
}

async function batchUpdate(body) {
  const tk = await token();
  const res = await fetch(`https://sheets.googleapis.com/v4/spreadsheets/${SHEET_ID}:batchUpdate`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${tk}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const j = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(`batchUpdate ${res.status}: ${JSON.stringify(j).slice(0, 300)}`);
  return j;
}

async function updateRange(rangeA1, values) {
  await api(`/values/${enc(rangeA1)}?valueInputOption=RAW`, { method: 'PUT', body: JSON.stringify({ values }) });
}

async function appendRow(values) {
  await api(`/values/${enc(q(REVIEW_TAB))}!A:${colLetter(REVIEW_HEADER.length - 1)}:append?valueInputOption=RAW&insertDataOption=INSERT_ROWS`, {
    method: 'POST',
    body: JSON.stringify({ values: [values] }),
  });
}

// 리뷰 탭 전체를 { id: {rating, note} } 맵으로 (탭 없으면 빈 맵)
export async function readReviews() {
  let all;
  try {
    const j = await api(`/values/${enc(q(REVIEW_TAB))}!A:D`);
    all = j.values || [];
  } catch (e) {
    if (/Unable to parse range/i.test(String(e.message || ''))) return {};
    throw e;
  }
  const map = {};
  for (let r = 1; r < all.length; r++) {
    const row = all[r] || [];
    const id = String(row[0] || '').replace(/^'/, '');
    if (id) map[id] = { rating: row[1] || '', note: row[2] || '' };
  }
  return map;
}

// id 기준 upsert. rating/note 중 전달된 것만 갱신. (읽기1 + 쓰기1 = 2콜)
export async function upsertReview(id, rating, note) {
  const all = await readReviewRows();
  let rowNum = -1, cur = null;
  for (let r = 1; r < all.length; r++) {
    const v = String((all[r] && all[r][0]) || '').replace(/^'/, '');
    if (v === String(id)) { rowNum = r + 1; cur = all[r]; break; }
  }
  const now = new Date().toISOString();
  if (rowNum === -1) {
    await appendRow([String(id), rating || '', note || '', now]);
    return { created: true };
  }
  const newRating = rating !== undefined ? rating : ((cur && cur[1]) || '');
  const newNote = note !== undefined ? note : ((cur && cur[2]) || '');
  await updateRange(`${q(REVIEW_TAB)}!A${rowNum}:D${rowNum}`, [[String(id), newRating, newNote, now]]);
  return { updated: true, row: rowNum };
}

export { SHEET_ID, TAB_NAME as TAB, REVIEW_TAB };
