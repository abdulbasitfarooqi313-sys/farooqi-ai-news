"""آج کی فلیش کا یوٹیوب Private اپلوڈ دوبارہ (ناکامی کی اصل وجہ کے ساتھ) — کامیاب ہو تو state میں درج، تاکہ ✅ کام کرے"""
import json, subprocess, sys
from pathlib import Path
sys.path.insert(0, ".")
from news import bulletin as B, youtube as yt
key = "2026-10-29-f"
d = json.loads(Path("state/flash_last.json").read_text())
subprocess.run(["gh", "release", "download", "flash-2026-10-29", "-p", "flash.mp4", "-O", "f.mp4", "--clobber"], check=True)
n = len(d["items"])
sd = {"youtube_title": (d.get("youtube_title") or f"اے آئی فلیش: دنیا بھر سے {n} خبریں")[:90] + " #shorts",
      "youtube_description": (d.get("summary", "") + "\n\n" + "\n".join(f"{i + 1}. {it['h']}" for i, it in enumerate(d["items"]))
                              + "\n\n🔗 ماخذ:\n" + "\n".join(f"{i + 1}. {it.get('source', '')} — {it.get('link', '')}" for i, it in enumerate(d["items"]) if it.get("link"))
                              + "\n\n🎬 Photos: Pexels / Pixabay\nآواز: اے آئی\n\n#shorts #اے_آئی #AINews #فاروقی_اے_آئی_نیوز")[:4900],
      "tags": list(dict.fromkeys((d.get("tags") or []) + ["اے آئی فلیش", "AI News Urdu", "فاروقی اے آئی نیوز", "shorts"]))}
print("UP desc len", len(sd["youtube_description"]), "| has <>:", any(c in sd["youtube_description"] for c in "<>"))
try:
    r = yt.upload(Path("f.mp4"), None, sd["youtube_title"], sd["youtube_description"], sd["tags"])
except Exception as e:
    print("UP ❌", str(e)[:400]); sys.exit(1)
print("UP ✅", r["url"], r["notes"])
st = json.loads(Path("state/news.json").read_text())
st["days"][key].update({"yt": r["id"], "yt_at": B._upload_dt().isoformat()})
Path("state/news.json").write_text(json.dumps(st, ensure_ascii=False, indent=1))
# run 2026-10-29T17:53:37
