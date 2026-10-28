"""چھوٹا نمونہ بلیٹن (ایک خبر) — Edge کی آواز (جیمنائی کا کوٹہ بچانے کو)۔ نتیجہ: out/preview.mp4
KEYED=1 / FORCE_KEY=1: میجنٹا خانے رہنے دیں (پیچھے کی ویڈیو بعد میں لگتی ہے) + out/tl.json, out/ranges.json"""
import json, os, sys, tempfile
from pathlib import Path
os.environ["NEWS_TTS"] = "edge"
import news.bulletin as b
import news.broll as br

d = json.load(open(sorted(Path("state").glob("script_*.json"))[-1], encoding="utf-8"))
st = next((s for s in d["stories"] if s.get("reporter")), d["stories"][0])
d["stories"] = [st]
d["ticker"] = (d.get("ticker") or [])[:4]
out = Path("out"); out.mkdir(exist_ok=True)
if os.environ.get("KEYED") == "1":
    b.ANCHOR_ON = False
    br.track = lambda d, tl, dest, tmp: Path("/dev/null")
    br.composite = lambda silent, broll, o: silent
with tempfile.TemporaryDirectory() as t:
    tmp = Path(t)
    try:
        for i, s_ in enumerate(d["stories"]):
            s_["_logo"] = b._logo(s_.get("domain") or "", tmp, i)
        b._site_shots(d, tmp)
        b.thumbnail(d, out / "thumb.jpg", tmp)
    except Exception as e:
        print("site shots/thumb skipped", e)
    audio, tl = b.build_audio(d, tmp)
    print("duration", tl["dur"])
    json.dump({"tl": {k: tl[k] for k in ("stories", "dur")}, "stories": [{"topic": s.get("topic")} for s in d["stories"]]},
              open(out / "tl.json", "w"), ensure_ascii=False)
    b.render_body(d, tl, audio, out / "preview.mp4", tmp)
print("done")
