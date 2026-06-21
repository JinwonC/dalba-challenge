import { scrapeContent } from './lib/apify.js';

const url = process.argv[2];
const content = await scrapeContent(url);
// Trim transcript for printing but keep enough to analyze.
console.log(JSON.stringify({
  platform: content.platform,
  title: content.title,
  author: content.author,
  durationSeconds: content.durationSeconds,
  stats: content.stats,
  hashtags: content.hashtags,
  thumbnail: content.thumbnail,
  description: content.description,
  transcript: content.transcript,
}, null, 2));
