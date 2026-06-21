import { detectPlatform, scrapeContent, scrapeTikTokComments } from './apify.js';
import { downloadVideo, fetchSubtitles } from './vision.js';
import { generateReport } from './report.js';
import { analyzeComments } from './comments.js';
import { saveVideo, pruneOldVideos } from './videos.js';

/** Extract the numeric TikTok video id from a URL (for the embed). */
export function tiktokVideoId(url) {
  const m = String(url).match(/\/video\/(\d+)/);
  return m ? m[1] : null;
}

/** Error with an attached HTTP status, so callers can map it cleanly. */
class HttpError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

/** Allowlist the hosts the report stage is allowed to fetch (anti-SSRF). */
function assertAllowedMediaUrl(videoUrl, subtitleUrl) {
  let vh;
  try {
    vh = new URL(videoUrl).hostname;
  } catch {
    throw new HttpError(400, 'Invalid videoUrl.');
  }
  if (vh !== 'api.apify.com') {
    throw new HttpError(400, 'videoUrl must be an Apify-hosted record.');
  }
  if (subtitleUrl) {
    let sh;
    try {
      sh = new URL(subtitleUrl).hostname;
    } catch {
      throw new HttpError(400, 'Invalid subtitleUrl.');
    }
    // TikTok serves subtitles from various owned CDNs (tiktok.com, tiktokcdn.com,
    // tiktokcdn-us.com, tiktokv.com, byteoversea.com, …).
    const TIKTOK_HOST = /(^|\.)(tiktok\.com|tiktokcdn\.com|tiktokcdn-us\.com|tiktokv\.com|byteoversea\.com|ibyteimg\.com)$/;
    if (!TIKTOK_HOST.test(sh) && sh !== 'api.apify.com') {
      throw new HttpError(400, `subtitleUrl host not allowed: ${sh}`);
    }
  }
}

/**
 * Stage 1 — scrape only (Apify). Fast-ish; returns everything the client needs
 * to render the video immediately + the media URLs for stage 2.
 */
export async function runScrape({ url }) {
  url = (url || '').trim();
  if (!url) throw new HttpError(400, 'Missing "url" in request body.');
  if (detectPlatform(url) !== 'tiktok') throw new HttpError(400, 'Provide a TikTok video link.');
  if (!process.env.APIFY_TOKEN) throw new HttpError(500, 'APIFY_TOKEN is not set on the server.');

  const content = await scrapeContent(url);
  if (!content.videoUrl) {
    throw new HttpError(502, 'Could not resolve a downloadable video URL from the scrape.');
  }

  const meta = {
    platform: 'tiktok',
    url: content.url,
    title: content.title,
    author: content.author,
    durationSeconds: content.durationSeconds,
    stats: content.stats,
    thumbnail: content.thumbnail,
    hashtags: content.hashtags,
  };

  return {
    meta,
    embed: { videoId: tiktokVideoId(url), url: content.url },
    media: { videoUrl: content.videoUrl, subtitleUrl: content.subtitleUrl || '' },
  };
}

/**
 * Stage 3 — scrape comments + analyze (Gemini text-only). Runs after stage 1 so it
 * doesn't contend with the main scraper on Apify's concurrency limit. Fast (~25s).
 */
export async function runComments({ url, meta = {} }) {
  url = (url || meta.url || '').trim();
  if (detectPlatform(url) !== 'tiktok') throw new HttpError(400, 'Provide a TikTok video link.');
  if (!process.env.APIFY_TOKEN) throw new HttpError(500, 'APIFY_TOKEN is not set on the server.');
  if (!process.env.GEMINI_API_KEY) throw new HttpError(500, 'GEMINI_API_KEY is not set on the server.');

  const comments = await scrapeTikTokComments(url, 40);
  if (!comments.length) {
    return { comments_analysis: await analyzeComments({ comments: [], meta }), count: 0 };
  }
  const comments_analysis = await analyzeComments({ comments, meta });
  return { comments_analysis, count: comments.length };
}

/**
 * Stage 2 — download media + Gemini report. Single Gemini attempt (the client
 * retries this endpoint on transient errors) so each call stays under the cap.
 */
export async function runReport({ videoUrl, subtitleUrl = '', meta = {} }) {
  if (!process.env.GEMINI_API_KEY) throw new HttpError(500, 'GEMINI_API_KEY is not set on the server.');
  if (!videoUrl) throw new HttpError(400, 'Missing "videoUrl".');
  assertAllowedMediaUrl(videoUrl, subtitleUrl);

  const [videoBuffer, transcriptVtt] = await Promise.all([
    downloadVideo(videoUrl),
    fetchSubtitles(subtitleUrl),
  ]);

  // Generate the report and (concurrently) persist the mp4 to the public store
  // so the player can stream/seek it — also lets history replay after deletion.
  const videoId = tiktokVideoId(meta.url || '');
  const [report, video] = await Promise.all([
    generateReport({ videoBuffer, transcriptVtt, meta, tries: 1 }),
    saveVideo(videoId, videoBuffer).catch((e) => { console.warn('Video save skipped:', e.message); return null; }),
  ]);
  // Keep the videos store bounded (delete old/overflow). Best-effort, quick.
  await pruneOldVideos();

  return { report, video };
}

/** Combined one-shot (used locally / for tests; too slow for a single serverless call). */
export async function runAnalysis({ url }) {
  const { meta, embed, media } = await runScrape({ url });
  const { report } = await runReport({ ...media, meta });
  return { platform: 'tiktok', meta: { ...meta, hasTranscript: undefined }, embed, report };
}

export { HttpError };
