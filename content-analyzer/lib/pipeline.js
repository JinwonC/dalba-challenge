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

/**
 * Full analyze pipeline: scrape (Apify) -> download mp4 + subtitles ->
 * Gemini scene report. Returns the API response object.
 * Throws HttpError(status, message) on failure.
 */
export async function runAnalysis({ url, language = 'Korean' }) {
  url = (url || '').trim();
  if (!url) throw new HttpError(400, 'Missing "url" in request body.');

  const platform = detectPlatform(url);
  if (platform !== 'tiktok') {
    throw new HttpError(400, 'Provide a TikTok video link.');
  }
  if (!process.env.GEMINI_API_KEY) {
    throw new HttpError(500, 'GEMINI_API_KEY is not set on the server.');
  }
  if (!process.env.APIFY_TOKEN) {
    throw new HttpError(500, 'APIFY_TOKEN is not set on the server.');
  }

  const content = await scrapeContent(url);
  if (!content.videoUrl) {
    throw new HttpError(502, 'Could not resolve a downloadable video URL from the scrape.');
  }

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

  return {
    platform,
    meta: { ...meta, hasTranscript: Boolean(transcriptVtt) },
    embed: { videoId: tiktokVideoId(url), url: content.url },
    report,
  };
}

export { HttpError };
