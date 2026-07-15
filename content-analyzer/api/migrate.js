import { migrateLegacyToUpstash } from '../lib/store.js';

// One-time recovery endpoint: imports legacy Vercel Blob reports into Upstash.
// Behind the site password gate. Safe to re-run (skips existing ids).
export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed. Use POST.' });
  try {
    const result = await migrateLegacyToUpstash();
    return res.status(200).json({ ok: true, ...result });
  } catch (err) {
    console.error('Migrate failed:', err);
    return res.status(500).json({ error: err.message || 'Migration failed.' });
  }
}
