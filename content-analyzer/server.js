import 'dotenv/config';
import express from 'express';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

import { detectPlatform, scrapeContent } from './lib/apify.js';
import { analyzeContent } from './lib/analyze.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());
app.use(express.static(join(__dirname, 'public')));

app.get('/api/health', (_req, res) => {
  res.json({
    ok: true,
    anthropic: Boolean(process.env.ANTHROPIC_API_KEY),
    apify: Boolean(process.env.APIFY_TOKEN),
  });
});

app.post('/api/analyze', async (req, res) => {
  const url = (req.body?.url || '').trim();
  if (!url) return res.status(400).json({ error: 'Missing "url" in request body.' });

  const platform = detectPlatform(url);
  if (!platform) {
    return res.status(400).json({ error: 'URL must be a YouTube or TikTok link.' });
  }

  try {
    const content = await scrapeContent(url);
    const analysis = await analyzeContent(content);
    res.json({
      platform,
      meta: {
        url: content.url,
        title: content.title,
        author: content.author,
        durationSeconds: content.durationSeconds,
        stats: content.stats,
        thumbnail: content.thumbnail,
        hashtags: content.hashtags,
        hasTranscript: Boolean(content.transcript),
      },
      analysis,
    });
  } catch (err) {
    console.error('Analyze failed:', err);
    res.status(502).json({ error: err.message || 'Analysis failed.' });
  }
});

app.listen(PORT, () => {
  console.log(`d'Alba Content Analyzer running at http://localhost:${PORT}`);
  if (!process.env.ANTHROPIC_API_KEY) console.warn('⚠  ANTHROPIC_API_KEY not set');
  if (!process.env.APIFY_TOKEN) console.warn('⚠  APIFY_TOKEN not set');
});
