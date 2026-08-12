#!/usr/bin/env python3
"""leaderboard.html + data/leaderboard.json -> 자체완결형 HTML (Claude Artifact용).

아티팩트는 외부 요청(폰트 CDN, fetch, 이미지)이 차단되므로 폰트 링크를 제거하고
시스템 폰트로 대체하며, JSON 데이터와 avatars/ 이미지를 페이지에 인라인한다.

사용법: python3 scripts/build_artifact.py <출력경로>
"""
import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
html = (ROOT / "leaderboard.html").read_text(encoding="utf-8")
data = json.loads((ROOT / "data" / "leaderboard.json").read_text(encoding="utf-8"))

# Artifact가 doctype/head/body 골격을 자동으로 씌우므로 래퍼 태그와
# 외부 폰트 링크를 제거하고 <title>/<style>/본문만 남긴다
DROP = ("fonts.googleapis.com", "<!DOCTYPE", "<html", "</html>",
        "<head>", "</head>", "<body>", "</body>", "<meta ")
lines = [l for l in html.splitlines(keepends=True)
         if not any(tok in l for tok in DROP)]
html = "".join(lines)
html = html.replace("<title>d'Alba Spotlight Day Challenge · Leaderboard</title>",
                    "<title>Spotlight Day Challenge</title>")
html = html.replace("'Playfair Display', serif", "Georgia, 'Times New Roman', serif")
html = html.replace("'Noto Sans', sans-serif",
                    "-apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif")

# 아바타 이미지를 data URI 맵으로 인라인
avatars = {}
for p in sorted((ROOT / "avatars").glob("*.jpg")):
    avatars[p.stem] = "data:image/jpeg;base64," + base64.b64encode(p.read_bytes()).decode()

# fetch 기반 로더를 인라인 데이터 렌더링으로 교체
start = html.index("  async function load()")
end_anchor = "setInterval(load, 5 * 60 * 1000); // re-fetch every 5 min; data itself refreshes hourly"
end = html.index(end_anchor) + len(end_anchor)
inline = ("  window.AVATARS = " + json.dumps(avatars) + ";\n"
          "  const DATA = " + json.dumps(data, ensure_ascii=False) + ";\n"
          "  render(DATA);")
html = html[:start] + inline + html[end:]

out = Path(sys.argv[1])
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(html, encoding="utf-8")
print(f"wrote {out} ({len(html)} bytes)")
