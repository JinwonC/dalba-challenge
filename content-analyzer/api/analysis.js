import { getAnalysis } from '../lib/store.js';

export default async function handler(req, res) {
  try {
    const id = String((req.query && req.query.id) || '');
    const rec = await getAnalysis(id);
    if (!rec) return res.status(404).json({ error: 'Not found.' });
    res.status(200).json(rec);
  } catch (err) {
    console.error('Analysis fetch failed:', err);
    res.status(502).json({ error: err.message || 'Fetch failed.' });
  }
}
