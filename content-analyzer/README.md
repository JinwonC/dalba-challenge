# d'Alba Content Analyzer

A small web app: paste a **YouTube** or **TikTok** link and get a **content breakdown** and **creative insights**.

It scrapes the video with [Apify](https://apify.com) (metadata, caption, hashtags, transcript/subtitles, stats) and then runs the data through **Claude** (`claude-opus-4-8`) to produce a structured analysis, rendered in a styled page that matches the d'Alba GLOW-TO-GOLD look.

```
content-analyzer/
├── server.js            Express server + /api/analyze endpoint
├── lib/
│   ├── apify.js         Platform detection + Apify scraping (YouTube + TikTok)
│   └── analyze.js       Claude structured-output analysis
├── public/index.html    Single-page frontend
└── .env.example         Copy to .env and fill in your keys
```

## Setup

Requires Node 20+.

```bash
cd content-analyzer
npm install
cp .env.example .env      # then add your ANTHROPIC_API_KEY and APIFY_TOKEN
npm start                 # → http://localhost:3000
```

Open <http://localhost:3000>, paste a link, hit **Analyze**.

## Keys you need

| Variable            | Where to get it                                                        |
| ------------------- | --------------------------------------------------------------------- |
| `ANTHROPIC_API_KEY` | <https://console.anthropic.com/>                                       |
| `APIFY_TOKEN`       | <https://console.apify.com/account/integrations>                      |

Both keys stay server-side — the browser never sees them.

## How it works

1. **`POST /api/analyze` `{ url }`** — the server detects YouTube vs TikTok.
2. **Scrape (Apify):** runs the configured actor for the platform and normalizes the result
   (title, author, caption/description, hashtags, transcript, stats, thumbnail). For YouTube it
   falls back to a dedicated transcript actor if the main one returns no captions.
3. **Analyze (Claude):** sends the normalized data to `claude-opus-4-8` with a JSON-schema
   `output_config.format`, so the response is always a valid, structured analysis object.
4. **Render:** the frontend displays the summary, hook analysis, content breakdown, and creative insights.

## Configuring the Apify actors

Defaults (override in `.env` if you prefer different actors):

| Variable                         | Default                                  |
| -------------------------------- | ---------------------------------------- |
| `APIFY_YOUTUBE_ACTOR`            | `streamers/youtube-scraper`              |
| `APIFY_YOUTUBE_TRANSCRIPT_ACTOR` | `pintostudio/youtube-transcript-scraper` |
| `APIFY_TIKTOK_ACTOR`            | `clockworks/tiktok-scraper`              |

Actor input field names vary between actors; the scraper normalizes common shapes. If you swap an
actor and a field comes back empty, adjust the `pick(...)` key lists in `lib/apify.js`.

## Notes

- Analysis covers **content breakdown** + **creative insights** (the two things requested). The
  analysis schema lives in `lib/analyze.js` — extend it (e.g. add a "d'Alba challenge fit" score)
  by adding properties to `ANALYSIS_SCHEMA` and the prompt, then rendering them in `index.html`.
- Scraping + analysis typically takes 30–90 seconds depending on the actor and video length.
