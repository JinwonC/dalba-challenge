import { detectPlatform, scrapeContent } from './apify.js';
import { downloadVideo, fetchSubtitles } from './vision.js';
import { generateReport } from './report.js';

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
    if (!/(^|\.)tiktokcdn(-us)?\.com$/.test(sh) && sh !== 'api.apify.com') {
      throw new HttpError(400, 'subtitleUrl host not allowed.');
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

  const report = await generateReport({ videoBuffer, transcriptVtt, meta, tries: 1 });
  return { report };
}

/** Combined one-shot (used locally / for tests; too slow for a single serverless call). */
export async function runAnalysis({ url }) {
  const { meta, embed, media } = await runScrape({ url });
  const { report } = await runReport({ ...media, meta });
  return { platform: 'tiktok', meta: { ...meta, hasTranscript: undefined }, embed, report };
}

export { HttpError };
