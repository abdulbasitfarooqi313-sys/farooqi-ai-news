"""چھوٹا نمونہ بلیٹن (ایک خبر) — اصل ڈیزائن، Edge کی آواز (جیمنائی کا کوٹہ بچانے کو)۔ نتیجہ: out/preview.mp4"""
import json, os, sys, tempfile
from pathlib import Path
os.environ["NEWS_TTS"] = "edge"
import news.bulletin as b

d = json.load(open(sorted(Path("state").glob("script_*.json"))[-1], encoding="utf-8"))
st = next((s for s in d["stories"] if s.get("reporter")), d["stories"][0])
d["stories"] = [st]
d["ticker"] = (d.get("ticker") or [])[:4]
out = Path("out"); out.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory() as t:
    tmp = Path(t)
    try:
        b._site_shots(d, tmp)
        b.thumbnail(d, out / "thumb.jpg", tmp)
    except Exception as e:
        print("site shots skipped", e)
    audio, tl = b.build_audio(d, tmp)
    print("duration", tl["dur"])
    b.render_body(d, tl, audio, out / "preview.mp4", tmp)
print("done")
