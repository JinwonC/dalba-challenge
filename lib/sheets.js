// Google Sheets 접근 (google-auth-library + REST fetch, 경량)
const { GoogleAuth } = require('google-auth-library');

const SHEET_ID = process.env.SHEET_ID || '1_qkd6LZ1wFoihhJSuYdabQ4iRbx-jsFYVxeGIoEb-_g';
const TAB = process.env.SHEET_TAB || '영상성과_신API테스트';
const enc = encodeURIComponent;

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

function colLetter(i) {
  let n = i + 1, s = '';
  while (n) { const r = (n - 1) % 26; s = String.fromCharCode(65 + r) + s; n = Math.floor((n - 1) / 26); }
  return s;
}

async function readAll() {
  const j = await api(`/values/${enc(TAB)}`);
  return j.values || [];
}
async function readHeader() {
  const j = await api(`/values/${enc(TAB + '!1:1')}`);
  return (j.values && j.values[0]) || [];
}
async function readColumn(letter) {
  const j = await api(`/values/${enc(TAB + '!' + letter + ':' + letter)}`);
  return j.values || [];
}
async function updateValues(rangeA1, values) {
  await api(`/values/${enc(rangeA1)}?valueInputOption=RAW`, { method: 'PUT', body: JSON.stringify({ values }) });
}
async function ensureReviewCols(header) {
  let idxRate = header.indexOf('평가');
  let idxNote = header.indexOf('특이사항');
  const h = header.slice();
  let changed = false;
  if (idxRate === -1) { idxRate = h.length; h.push('평가'); changed = true; }
  if (idxNote === -1) { idxNote = h.length; h.push('특이사항'); changed = true; }
  if (changed) await updateValues(`${TAB}!A1:${colLetter(h.length - 1)}1`, [h]);
  return { idxRate, idxNote };
}

module.exports = { readAll, readHeader, readColumn, updateValues, ensureReviewCols, colLetter, SHEET_ID, TAB };
