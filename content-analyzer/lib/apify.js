import { ApifyClient } from 'apify-client';

const YOUTUBE_ACTOR = process.env.APIFY_YOUTUBE_ACTOR || 'streamers/youtube-scraper';
const YOUTUBE_TRANSCRIPT_ACTOR =
  process.env.APIFY_YOUTUBE_TRANSCRIPT_ACTOR || 'pintostudio/youtube-transcript-scraper';
const TIKTOK_ACTOR = process.env.APIFY_TIKTOK_ACTOR || 'clockworks/tiktok-scraper';
const TIKTOK_COMMENTS_ACTOR = process.env.APIFY_TIKTOK_COMMENTS_ACTOR || 'clockworks/tiktok-comments-scraper';

let _client = null;
function client() {
  if (!_client) {
    if (!process.env.APIFY_TOKEN) {
      throw new Error('APIFY_TOKEN is not set. Add it to your .env file.');
    }
    _client = new ApifyClient({ token: process.env.APIFY_TOKEN });
  }
  return _client;
}

/** Detect which platform a URL belongs to. Returns 'youtube' | 'tiktok' | null. */
export function detectPlatform(url) {
  let host;
  try {
    host = new URL(url).hostname.replace(/^www\./, '').toLowerCase();
  } catch {
    return null;
  }
  if (host.endsWith('youtube.com') || host === 'youtu.be' || host.endsWith('youtube-nocookie.com')) {
    return 'youtube';
  }
  if (host.endsWith('tiktok.com')) {
    return 'tiktok';
  }
  return null;
}

/** Run an actor and return its dataset items. */
async function runActor(actorId, input) {
  const run = await client().actor(actorId).call(input);
  const { items } = await client().dataset(run.defaultDatasetId).listItems();
  return items;
}

/** Pull the first non-empty value across a list of candidate keys. */
function pick(obj, keys) {
  for (const k of keys) {
    const v = obj?.[k];
    if (v !== undefined && v !== null && v !== '') return v;
  }
  return undefined;
}

/** Extract hashtags from text and/or a structured hashtags array. */
function extractHashtags(text, structured) {
  const tags = new Set();
  if (Array.isArray(structured)) {
    for (const h of structured) {
      const name = typeof h === 'string' ? h : h?.name || h?.title;
      if (name) tags.add(String(name).replace(/^#/, ''));
    }
  }
  if (typeof text === 'string') {
    for (const m of text.matchAll(/#([\p{L}\p{N}_]+)/gu)) {
      tags.add(m[1]);
    }
  }
  return [...tags];
}

/** Join transcript/subtitle segments into a single string. */
function flattenTranscript(raw) {
  if (!raw) return '';
  if (typeof raw === 'string') return raw.trim();
  if (Array.isArray(raw)) {
    return raw
      .map((seg) => (typeof seg === 'string' ? seg : seg?.text || seg?.caption || ''))
      .filter(Boolean)
      .join(' ')
      .trim();
  }
  return '';
}

async function scrapeYouTube(url) {
  const items = await runActor(YOUTUBE_ACTOR, {
    startUrls: [{ url }],
    maxResults: 1,
    maxResultsShorts: 1,
    subtitlesLanguage: 'en',
    downloadSubtitles: true,
  });
  const v = items[0] || {};

  let transcript = flattenTranscript(pick(v, ['subtitles', 'transcript', 'captions']));

  // Fall back to a dedicated transcript actor if the main one returned none.
  if (!transcript) {
    try {
      const t = await runActor(YOUTUBE_TRANSCRIPT_ACTOR, { videoUrl: url, url });
      transcript = flattenTranscript(t[0]?.transcript || t[0]?.data || t);
    } catch {
      /* transcript is best-effort */
    }
  }

  const description = pick(v, ['text', 'description']) || '';
  return {
    platform: 'youtube',
    url,
    title: pick(v, ['title']) || '',
    author: pick(v, ['channelName', 'channelUsername', 'author']) || '',
    description,
    transcript,
    hashtags: extractHashtags(description, v.hashtags),
    durationSeconds: pick(v, ['duration', 'lengthSeconds']),
    stats: {
      views: pick(v, ['viewCount', 'views']),
      likes: pick(v, ['likes', 'likeCount']),
      comments: pick(v, ['commentsCount', 'commentCount']),
    },
    thumbnail: pick(v, ['thumbnailUrl', 'thumbnail']),
    raw: v,
  };
}

/** Pick the best subtitle link (prefer English ASR) from videoMeta.subtitleLinks. */
function pickSubtitleUrl(videoMeta) {
  const links = videoMeta?.subtitleLinks;
  if (!Array.isArray(links) || links.length === 0) return undefined;
  const isEng = (l) => /^eng/i.test(l?.language || '');
  const eng = links.find(isEng);
  const chosen = eng || links[0];
  return chosen?.downloadLink || chosen?.tiktokLink;
}

async function scrapeTikTok(url) {
  const items = await runActor(TIKTOK_ACTOR, {
    postURLs: [url],
    resultsPerPage: 1,
    shouldDownloadSubtitles: true,
    shouldDownloadVideos: true,
    shouldDownloadCovers: false,
  });
  const v = items[0] || {};

  const caption = pick(v, ['text', 'description', 'desc']) || '';
  const transcript = flattenTranscript(
    pick(v, ['subtitles', 'transcript', 'videoSubtitles'])
  );
  // mediaUrls (Apify-hosted mp4) is the reliable download source.
  const videoUrl =
    (Array.isArray(v.mediaUrls) && v.mediaUrls[0]) ||
    pick(v?.videoMeta || v, ['downloadAddr', 'playAddr']) ||
    pick(v, ['videoUrl']);
  const subtitleUrl = pickSubtitleUrl(v?.videoMeta);

  return {
    platform: 'tiktok',
    videoUrl,
    subtitleUrl,
    url,
    title: caption.split('\n')[0] || '',
    author: pick(v?.authorMeta || v, ['name', 'nickName', 'authorName', 'author']) || '',
    description: caption,
    transcript,
    hashtags: extractHashtags(caption, v.hashtags),
    durationSeconds: pick(v?.videoMeta || v, ['duration']),
    stats: {
      views: pick(v, ['playCount', 'views']),
      likes: pick(v, ['diggCount', 'likes']),
      comments: pick(v, ['commentCount', 'comments']),
      shares: pick(v, ['shareCount', 'shares']),
    },
    thumbnail: pick(v?.videoMeta || v, ['coverUrl', 'cover', 'originalCoverUrl']),
    raw: v,
  };
}

/** Scrape top TikTok comments for a post. Best-effort: returns [] on failure. */
export async function scrapeTikTokComments(url, max = 40) {
  try {
    const items = await runActor(TIKTOK_COMMENTS_ACTOR, {
      postURLs: [url],
      commentsPerPost: max,
      maxRepliesPerComment: 0,
    });
    return items
      .map((c) => ({
        text: pick(c, ['text', 'comment']) || '',
        likes: pick(c, ['diggCount', 'likesCount', 'likes']) ?? 0,
        author: pick(c, ['uniqueId', 'username', 'nickName']) || '',
        likedByAuthor: Boolean(c.likedByAuthor),
        pinned: Boolean(c.pinnedByAuthor || c.pinned),
        replies: pick(c, ['replyCommentTotal', 'repliesCount']) ?? 0,
      }))
      .filter((c) => c.text)
      .sort((a, b) => (b.likes || 0) - (a.likes || 0));
  } catch (e) {
    console.warn('Comment scrape skipped:', e.message);
    return [];
  }
}

/** Scrape a YouTube or TikTok URL into a normalized content object. */
export async function scrapeContent(url) {
  const platform = detectPlatform(url);
  if (platform === 'youtube') return scrapeYouTube(url);
  if (platform === 'tiktok') return scrapeTikTok(url);
  throw new Error('Unsupported URL. Provide a YouTube or TikTok link.');
}
