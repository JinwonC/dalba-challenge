import 'dotenv/config';
import express from 'express';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

import { runAnalysis, HttpError } from './lib/pipeline.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());
app.use(express.static(join(__dirname, 'public')));

app.get('/api/health', (_req, res) => {
  res.json({
    ok: true,
    apify: Boolean(process.env.APIFY_TOKEN),
    gemini: Boolean(process.env.GEMINI_API_KEY),
  });
});

app.post('/api/analyze', async (req, res) => {
  try {
    const result = await runAnalysis({ url: req.body?.url, language: req.body?.language });
    res.json(result);
  } catch (err) {
    const status = err instanceof HttpError ? err.status : 502;
    if (status >= 500) console.error('Analyze failed:', err);
    res.status(status).json({ error: err.message || 'Analysis failed.' });
  }
});

app.listen(PORT, () => {
  console.log(`d'Alba Content Analyzer running at http://localhost:${PORT}`);
  if (!process.env.APIFY_TOKEN) console.warn('⚠  APIFY_TOKEN not set — scraping will fail');
  if (!process.env.GEMINI_API_KEY) console.warn('⚠  GEMINI_API_KEY not set — report generation will fail');
});
