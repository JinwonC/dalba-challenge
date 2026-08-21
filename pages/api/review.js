// POST /api/review  { id, rating, note }  → 별도 리뷰 탭에 upsert
import { upsertReview } from '../../lib/sheets';

export default async function handler(req, res) {
  if (process.env.APP_KEY && req.headers['x-app-key'] !== process.env.APP_KEY) {
    return res.status(401).json({ error: 'unauthorized' });
  }
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST only' });
  const { id, rating, note } = req.body || {};
  if (!id) return res.status(400).json({ error: 'id 필요' });
  try {
    const r = await upsertReview(String(id), rating, note);
    res.status(200).json({ ok: true, ...r });
  } catch (e) {
    res.status(500).json({ error: String((e && e.message) || e) });
  }
}
