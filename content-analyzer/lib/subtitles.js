/** Parse WebVTT into timed cues: [{ start, end, text }] (seconds). */
export function parseVtt(vtt) {
  if (!vtt || typeof vtt !== 'string') return [];
  const toSec = (ts) => {
    const t = ts.trim().replace(',', '.');
    const p = t.split(':').map(parseFloat);
    if (p.some(isNaN)) return null;
    return p.length === 3 ? p[0] * 3600 + p[1] * 60 + p[2] : p[0] * 60 + p[1];
  };
  const cues = [];
  const blocks = vtt.replace(/\r/g, '').split(/\n\n+/);
  const TS = '(\\d{1,2}:\\d{2}:\\d{2}[.,]\\d{3}|\\d{1,2}:\\d{2}[.,]\\d{3})';
  const re = new RegExp(`${TS}\\s*-->\\s*${TS}`);
  for (const b of blocks) {
    const lines = b.split('\n').filter((l) => l.trim() !== '' && l.trim() !== 'WEBVTT');
    const idx = lines.findIndex((l) => re.test(l));
    if (idx === -1) continue;
    const m = lines[idx].match(re);
    const start = toSec(m[1]);
    const end = toSec(m[2]);
    const text = lines.slice(idx + 1).join(' ').replace(/<[^>]+>/g, '').trim();
    if (start == null || !text) continue;
    cues.push({ start, end, text });
  }
  return cues;
}
