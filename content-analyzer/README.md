# d'Alba Content Analyzer

A small web app: paste a **TikTok** link and get a **two-column report** — the **TikTok video on the left**, a **scene-by-scene breakdown** (Scene · Visual Description · Audio Script) plus **creative insights** on the right.

It scrapes the video with [Apify](https://apify.com) (metadata, caption, hashtags, **time-coded subtitles**, stats, and an mp4), then **Gemini watches the actual video** and — combined with the time-coded transcript — produces a **structured scene report** (summary, scene table, insights, d'Alba relevance) via JSON structured output. The left column embeds the original clip with TikTok's official embed. Styled to match the d'Alba GLOW-TO-GOLD look.

```
content-analyzer/
├── server.js            Express server + /api/analyze endpoint
├── lib/
│   ├── apify.js         Platform detection + Apify scraping (mp4 + time-coded subtitles)
│   ├── vision.js        Video/subtitle download helpers + standalone Gemini visual rundown
│   ├── report.js        Gemini structured scene-by-scene report (summary, scenes, insights)
│   └── analyze.js       (optional) Claude structured-output analysis — not used by default
├── public/index.html    Single-page two-column frontend (left: TikTok embed, right: report)
└── .env.example         Copy to .env and fill in your keys
```

> **Note:** the default pipeline uses **Gemini only** for the report (no Anthropic key required). YouTube support remains in `apify.js`/`analyze.js` but the new scene-report UI is TikTok-focused.

## Visual analysis (what's on screen)

If you set `GEMINI_API_KEY`, the app downloads the TikTok video and sends it to **Gemini**, which
watches the frames and reports **on-screen text, what the person is doing, and the background/setting** —
things a transcript can't capture. That visual rundown is fed into the Claude analysis (so the
breakdown's *Setting & Background*, *Actions*, and *On-screen Text* fields are grounded in the actual
video) and also shown verbatim in a "Visual Analysis" section. Without a Gemini key the app still works
on caption + transcript only.

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

| Variable            | Required? | Where to get it                                                       |
| ------------------- | --------- | -------------------------------------------------------------------- |
| `APIFY_TOKEN`       | yes       | <https://console.apify.com/account/integrations>                    |
| `GEMINI_API_KEY`    | yes       | <https://aistudio.google.com/apikey> (watches the video + writes the report) |
| `ANTHROPIC_API_KEY` | optional  | <https://console.anthropic.com/> (only for the legacy Claude analysis path) |

All keys stay server-side — the browser never sees them.

## How it works

1. **`POST /api/analyze` `{ url, language }`** — the server validates the TikTok link.
2. **Scrape (Apify):** runs `clockworks/tiktok-scraper` with video + subtitle download, and
   normalizes the result (title, author, caption, hashtags, **time-coded VTT subtitle URL**,
   stats, thumbnail, and an Apify-hosted **mp4 URL**).
3. **Fetch media:** downloads the mp4 (for Gemini to watch) and the time-coded subtitles in parallel.
4. **Report (Gemini):** `lib/report.js` uploads the mp4 via the Files API and asks Gemini, with a
   JSON `responseSchema`, to segment the video into scenes and return
   `{ summary, scenes[], insights, dalba_relevance }` in the requested language.
5. **Render:** the frontend shows the **TikTok embed on the left** and the **scene table + insights
   on the right**.

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
