import 'dotenv/config';
import express from 'express';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

import { detectPlatform, scrapeContent } from './lib/apify.js';
import { downloadVideo, fetchSubtitles } from './lib/vision.js';
import { generateReport } from './lib/report.js';

/** Extract the numeric TikTok video id from a URL (for the embed). */
function tiktokVideoId(url) {
  const m = String(url).match(/\/video\/(\d+)/);
  return m ? m[1] : null;
}

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
    gemini: Boolean(process.env.GEMINI_API_KEY),
  });
});

app.post('/api/analyze', async (req, res) => {
  const url = (req.body?.url || '').trim();
  if (!url) return res.status(400).json({ error: 'Missing "url" in request body.' });

  const platform = detectPlatform(url);
  if (!platform) {
    return res.status(400).json({ error: 'URL must be a YouTube or TikTok link.' });
  }

  const language = (req.body?.language || 'Korean').trim();

  try {
    if (!process.env.GEMINI_API_KEY) {
      return res.status(500).json({ error: 'GEMINI_API_KEY is not set on the server.' });
    }

    const content = await scrapeContent(url);
    if (!content.videoUrl) {
      return res.status(502).json({ error: 'Could not resolve a downloadable video URL from the scrape.' });
    }

    // Download the mp4 (for Gemini to watch) and the time-coded subtitles in parallel.
    const [videoBuffer, transcriptVtt] = await Promise.all([
      downloadVideo(content.videoUrl),
      fetchSubtitles(content.subtitleUrl),
    ]);

    const meta = {
      platform,
      url: content.url,
      title: content.title,
      author: content.author,
      durationSeconds: content.durationSeconds,
      stats: content.stats,
      thumbnail: content.thumbnail,
      hashtags: content.hashtags,
    };

    const report = await generateReport({ videoBuffer, transcriptVtt, meta, language });

    res.json({
      platform,
      meta: { ...meta, hasTranscript: Boolean(transcriptVtt) },
      embed: { videoId: tiktokVideoId(url), url: content.url },
      report,
    });
  } catch (err) {
    console.error('Analyze failed:', err);
    res.status(502).json({ error: err.message || 'Analysis failed.' });
  }
});

app.listen(PORT, () => {
  console.log(`d'Alba Content Analyzer running at http://localhost:${PORT}`);
  if (!process.env.APIFY_TOKEN) console.warn('⚠  APIFY_TOKEN not set — scraping will fail');
  if (!process.env.GEMINI_API_KEY) console.warn('⚠  GEMINI_API_KEY not set — report generation will fail');
});
