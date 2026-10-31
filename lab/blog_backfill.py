"""ایک بار: اب تک کا مواد بلاگ پر — شائع شدہ (ٹریلر، 29 اکتوبر کی فلیش) = پوسٹ؛ پرانے بلیٹن (یوٹیوب پر نہیں گئے) = ڈرافٹ آرکائیو"""
import datetime as dt, html, json, sys
from pathlib import Path
sys.path.insert(0, ".")
from news import blog
from news.base import read_json

now = dt.datetime.now(blog.TZ)
st = read_json(blog.STATE) if blog.STATE.exists() else {}
done = st.get("posts", {})

# 1) ٹریلر
if "trailer" not in done:
    sys.path.insert(0, "lab/trailer")
    import re
    src = Path("lab/trailer/trailer.py").read_text(encoding="utf-8")
    lines = re.findall(r'\("s\d", "([^"]+)"\)', src)
    body = "".join(f"<p>{html.escape(l)}</p>" for l in lines)
    blog.QUEUE.mkdir(parents=True, exist_ok=True)
    (blog.QUEUE / "trailer.json").write_text(json.dumps({"kind": "trailer", "title": "فاروقی اے آئی نیوز میں خوش آمدید — مصنوعی ذہانت کی دنیا، آسان اردو میں",
        "labels": ["چینل کا تعارف"], "html": blog._video_block("فاروقی اے آئی نیوز") + "\n<h2>ہمارا تعارف</h2>" + body}, ensure_ascii=False), encoding="utf-8")
    print("BLOG", "trailer", blog.publish("trailer", "QBPSjzBz4sA", now))

# 2) 29 اکتوبر کی اے آئی فلیش (یوٹیوب پر پبلک)
if "2026-10-29-f" not in done:
    d = read_json(Path("state/flash_last.json"))
    blog.prepare("flash", "2026-10-29-f", d, {"youtube_title": d.get("youtube_title", "اے آئی فلیش")})
    print("BLOG", "flash", blog.publish("2026-10-29-f", "zcly-QYVNRo", now))

# 3) پرانے بلیٹن — یوٹیوب پر نہیں گئے: صرف آرکائیو ڈرافٹ (ویڈیو کے بغیر)
vb = blog._video_block
blog._video_block = lambda title: ""
for f in sorted(Path("lab/backfill").glob("script_*.json")):
    day = f.stem.split("_")[1]
    key = f"archive-{day}"
    if (blog.QUEUE / f"{key}.json").exists():
        continue
    d = read_json(f)
    blog.prepare("bulletin", key, d, {"youtube_title": (d.get("youtube_title") or "بلیٹن") + f" — {day}"})
    rec = read_json(blog.QUEUE / f"{key}.json")
    print("BLOG draft", key, rec.get("pid"))
blog._video_block = vb
