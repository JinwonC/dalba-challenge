/** Render a generated guide into readable plain text (for Drive export). */
export function guideToPlainText(guide = {}, meta = {}) {
  const g = guide || {};
  let t = `Contents Brief\n${g.product_line || ''}\n[ Shooting Guide ]\n\n`;
  if (meta.manager) t += `담당자: ${meta.manager}\n`;
  if (g.creator) t += `레퍼런스 크리에이터: @${g.creator}\n`;
  t += `\n`;

  if (g.structure_summary) t += `■ 구조 요약\n${g.structure_summary}\n\n`;
  if (g.reference_note) t += `핵심 지시: ${g.reference_note}\n\n`;
  if ((g.common_patterns || []).length) {
    t += `■ 반복 공통 패턴 (A의 바이럴 공식)\n`;
    g.common_patterns.forEach((p) => { t += `  · [${p.aspect}] ${p.finding}\n`; });
    t += `\n`;
  }

  if ((g.reference_videos || []).length) {
    t += `■ 레퍼런스 영상\n`;
    g.reference_videos.forEach((v) => { t += `  - ${v.label}: ${v.url}\n`; });
    t += `\n`;
  }

  if ((g.hook_options || []).length) {
    t += `■ 훅 3안 (A/B 테스트용)\n`;
    g.hook_options.forEach((h) => {
      t += `  [${h.label}]\n`;
      if (h.text_overlay) t += `    화면텍스트: ${h.text_overlay}\n`;
      (h.say || []).forEach((l) => { t += `    Say: ${l.text}\n`; });
      if (h.rationale) t += `    (${h.rationale})\n`;
    });
    t += `\n`;
  }

  (g.steps || []).forEach((s, i) => {
    t += `── Step ${i + 1} — ${s.name || ''} ──\n`;
    if (s.directive) t += `[촬영] ${s.directive}\n`;
    if (s.text_overlay) t += `[화면텍스트] ${s.text_overlay}\n`;
    (s.say || []).forEach((line) => { t += `  Say: ${line.text}\n`; });
    if (s.reference_hint) t += `  (참고: ${s.reference_hint})\n`;
    if (s.our_angle) t += `  (우리 소구: ${s.our_angle})\n`;
    t += `\n`;
  });

  if ((g.tips || []).length) {
    t += `■ Tips\n`;
    g.tips.forEach((tip) => { t += `  - ${tip.text}\n`; });
    t += `\n`;
  }

  const p = g.product || {};
  if (p.name || (p.bullets || []).length) {
    t += `■ Product — ${p.name || ''}\n`;
    (p.bullets || []).forEach((b) => { t += `  ✔ ${[b.highlight, b.text].filter(Boolean).join(' ')}\n`; });
  }
  return t;
}
