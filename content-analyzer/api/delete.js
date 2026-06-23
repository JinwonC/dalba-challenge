import { deleteAnalysis } from '../lib/store.js';

export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed. Use POST.' });
  try {
    const body = typeof req.body === 'string' ? JSON.parse(req.body || '{}') : (req.body || {});
    const ok = await deleteAnalysis(String(body.id || ''));
    res.status(200).json({ ok });
  } catch (err) {
    console.error('Delete failed:', err);
    res.status(502).json({ error: err.message || 'Delete failed.' });
  }
}
