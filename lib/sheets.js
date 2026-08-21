// Google Sheets 접근 헬퍼 (서비스 계정)
const { google } = require('googleapis');

const SHEET_ID = process.env.SHEET_ID || '1_qkd6LZ1wFoihhJSuYdabQ4iRbx-jsFYVxeGIoEb-_g';
const TAB = process.env.SHEET_TAB || '영상성과_신API테스트';

function getSheets() {
  const raw = process.env.GOOGLE_SERVICE_ACCOUNT_JSON;
  if (!raw) throw new Error('GOOGLE_SERVICE_ACCOUNT_JSON env 없음');
  const creds = JSON.parse(raw);
  const auth = new google.auth.JWT(
    creds.client_email,
    null,
    (creds.private_key || '').replace(/\\n/g, '\n'),
    ['https://www.googleapis.com/auth/spreadsheets']
  );
  return google.sheets({ version: 'v4', auth });
}

// 0-based index -> A1 컬럼 문자
function colLetter(i) {
  let n = i + 1;
  let s = '';
  while (n) {
    const r = (n - 1) % 26;
    s = String.fromCharCode(65 + r) + s;
    n = Math.floor((n - 1) / 26);
  }
  return s;
}

async function readAll() {
  const sheets = getSheets();
  const res = await sheets.spreadsheets.values.get({ spreadsheetId: SHEET_ID, range: TAB });
  return res.data.values || [];
}

async function readHeader(sheets) {
  const res = await sheets.spreadsheets.values.get({ spreadsheetId: SHEET_ID, range: `${TAB}!1:1` });
  return (res.data.values && res.data.values[0]) || [];
}

// 평가/특이사항 컬럼이 없으면 헤더에 추가하고 인덱스를 돌려준다
async function ensureReviewCols(sheets, header) {
  let idxRate = header.indexOf('평가');
  let idxNote = header.indexOf('특이사항');
  const h = header.slice();
  let changed = false;
  if (idxRate === -1) { idxRate = h.length; h.push('평가'); changed = true; }
  if (idxNote === -1) { idxNote = h.length; h.push('특이사항'); changed = true; }
  if (changed) {
    await sheets.spreadsheets.values.update({
      spreadsheetId: SHEET_ID,
      range: `${TAB}!A1:${colLetter(h.length - 1)}1`,
      valueInputOption: 'RAW',
      requestBody: { values: [h] },
    });
  }
  return { idxRate, idxNote };
}

module.exports = { getSheets, colLetter, readAll, readHeader, ensureReviewCols, SHEET_ID, TAB };
