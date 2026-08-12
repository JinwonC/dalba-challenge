#!/usr/bin/env python3
"""data/leaderboard.json의 크리에이터 TikTok 아바타를 avatars/ 에 내려받는다.

이미 있는 파일은 건너뛰므로 시간당 갱신에서 반복 실행해도 새 참가자 것만
받아온다. 소스는 unavatar.io (TikTok 공개 프로필 사진 프록시).

사용법: python3 scripts/fetch_avatars.py
"""
import io
import json
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageOps

SIZE = 128  # 표시 최대 30~72px이므로 128px 정사각형이면 레티나에도 충분


def shrink(body: bytes) -> bytes:
    img = Image.open(io.BytesIO(body))
    img = ImageOps.exif_transpose(img).convert("RGB")
    img = ImageOps.fit(img, (SIZE, SIZE))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=85)
    return out.getvalue()

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "avatars"
OUT.mkdir(exist_ok=True)

rows = json.loads((ROOT / "data" / "leaderboard.json").read_text(encoding="utf-8"))["leaderboard"]

for row in rows:
    handle = row["handle"]
    dest = OUT / f"{handle}.jpg"
    if dest.exists():
        continue
    url = f"https://unavatar.io/tiktok/{urllib.parse.quote(handle)}?fallback=false"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read()
        if resp.headers.get_content_type().startswith("image/") and len(body) > 500:
            body = shrink(body)
            dest.write_bytes(body)
            print(f"fetched {handle} ({len(body)} bytes)")
        else:
            print(f"skip {handle}: not an image")
    except Exception as e:  # 404(프로필 없음)나 일시 오류 — 다음 실행에서 재시도
        print(f"skip {handle}: {e}")
