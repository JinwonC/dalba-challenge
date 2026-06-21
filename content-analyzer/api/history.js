import { listAnalyses } from '../lib/store.js';

export default async function handler(_req, res) {
  try {
    res.status(200).json({ items: await listAnalyses() });
  } catch (err) {
    console.error('History failed:', err);
    res.status(502).json({ error: err.message || 'History failed.' });
  }
}
