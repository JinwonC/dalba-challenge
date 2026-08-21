// POST /api/review  { id, rating, note }
const { getSheets, colLetter, readHeader, ensureReviewCols, SHEET_ID, TAB } = require('../../lib/sheets');

module.exports = async function handler(req, res) {
  if (process.env.APP_KEY && req.headers['x-app-key'] !== process.env.APP_KEY) {
    return res.status(401).json({ error: 'unauthorized' });
  }
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST only' });
  const { id, rating, note } = req.body || {};
  if (!id) return res.status(400).json({ error: 'id 필요' });
  try {
    const sheets = getSheets();
    const header = await readHeader(sheets);
    const idCol = header.indexOf('id');
    if (idCol === -1) return res.status(500).json({ error: '헤더에 id 없음' });

    // id 컬럼만 읽어 행 위치 탐색
    const idColLetter = colLetter(idCol);
    const colRes = await sheets.spreadsheets.values.get({
      spreadsheetId: SHEET_ID, range: `${TAB}!${idColLetter}:${idColLetter}`,
    });
    const ids = colRes.data.values || [];
    let rowNum = -1;
    for (let r = 1; r < ids.length; r++) {
      const v = String((ids[r] && ids[r][0]) || '').replace(/^'/, '');
      if (v === String(id)) { rowNum = r + 1; break; }
    }
    if (rowNum === -1) return res.status(404).json({ error: '영상 없음' });

    const { idxRate, idxNote } = await ensureReviewCols(sheets, header);
    const data = [];
    if (rating !== undefined) data.push({ range: `${TAB}!${colLetter(idxRate)}${rowNum}`, values: [[rating]] });
    if (note !== undefined) data.push({ range: `${TAB}!${colLetter(idxNote)}${rowNum}`, values: [[note]] });
    if (data.length) {
      await sheets.spreadsheets.values.batchUpdate({
        spreadsheetId: SHEET_ID,
        requestBody: { valueInputOption: 'RAW', data },
      });
    }
    res.status(200).json({ ok: true, row: rowNum });
  } catch (e) {
    res.status(500).json({ error: String((e && e.message) || e) });
  }
};
