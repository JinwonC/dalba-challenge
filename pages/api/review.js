// POST /api/review  { id, rating, note }
import { readHeader, readColumn, updateValues, ensureReviewCols, colLetter, TAB } from '../../lib/sheets';

export default async function handler(req, res) {
  if (process.env.APP_KEY && req.headers['x-app-key'] !== process.env.APP_KEY) {
    return res.status(401).json({ error: 'unauthorized' });
  }
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST only' });
  const { id, rating, note } = req.body || {};
  if (!id) return res.status(400).json({ error: 'id 필요' });
  try {
    const header = await readHeader();
    const idCol = header.indexOf('id');
    if (idCol === -1) return res.status(500).json({ error: '헤더에 id 없음' });
    const ids = await readColumn(colLetter(idCol));
    let rowNum = -1;
    for (let r = 1; r < ids.length; r++) {
      const v = String((ids[r] && ids[r][0]) || '').replace(/^'/, '');
      if (v === String(id)) { rowNum = r + 1; break; }
    }
    if (rowNum === -1) return res.status(404).json({ error: '영상 없음' });
    const { idxRate, idxNote } = await ensureReviewCols(header);
    if (rating !== undefined) await updateValues(`${TAB}!${colLetter(idxRate)}${rowNum}`, [[rating]]);
    if (note !== undefined) await updateValues(`${TAB}!${colLetter(idxNote)}${rowNum}`, [[note]]);
    res.status(200).json({ ok: true, row: rowNum });
  } catch (e) {
    res.status(500).json({ error: String((e && e.message) || e) });
  }
}
