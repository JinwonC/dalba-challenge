export default function handler(_req, res) {
  res.status(200).json({
    ok: true,
    apify: Boolean(process.env.APIFY_TOKEN),
    gemini: Boolean(process.env.GEMINI_API_KEY),
  });
}
