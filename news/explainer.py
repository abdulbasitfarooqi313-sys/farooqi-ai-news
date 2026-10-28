"""«ایکسپلینر» انداز (بغیر اینکر، بڑے ڈیجیٹل نیوز چینلوں جیسا صاف اسلوب — اپنی پہچان کے ساتھ، کسی کی نقل نہیں):
پوری اسکرین پر وہی جس کی بات ہو رہی ہے (عنوان، سرخی + لوگو، اصل ویب سائٹ، اہم نکات، مقام، خبر سے متعلق ویڈیو)
اور نیچے اردو کیپشن۔ ترتیب اور آواز وہی جو build_audio بناتا ہے (tl["utt"])۔ NEWS_STYLE=explainer سے چلتا ہے۔
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

from . import broll as br

ROOT = Path(__file__).resolve().parent.parent
A = ROOT / "studio"
FPS = 25
U = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def _chunks(text: str, t0: float, t1: float, max_words: int = 9) -> list[dict]:
    """جملہ → کیپشن کے ٹکڑے (وقت حروف کے تناسب سے)"""
    parts = [p.strip() for p in re.split(r"(?<=[۔؟!،,:])\s+", text.strip()) if p.strip()]
    out = []
    for p in parts:
        w = p.split()
        for i in range(0, len(w), max_words):
            out.append(" ".join(w[i:i + max_words]))
    if not out:
        return []
    total = sum(len(x) + 4 for x in out)
    caps, t = [], t0
    for x in out:
        du = (t1 - t0) * (len(x) + 4) / total
        caps.append({"t0": round(t, 2), "t1": round(t + du, 2), "text": x})
        t += du
    return caps


def plan(d: dict, tl: dict, date: str) -> tuple[list, list, list]:
    """(مناظر، کیپشن، پسِ منظر ویڈیو کے حصے)"""
    sts, utt = d["stories"], tl["utt"]
    scenes, segs = [], []

    def scene(t0, kind, q=None, **kw):
        scenes.append({"t0": round(t0, 2), "kind": kind, **kw})
        segs.append((t0, q or br.GENERIC))

    first_h = tl["hcards"][0]["t0"] - 0.3 if tl["hcards"] else utt[0]["t1"]
    scene(0, "title", br.GENERIC, kicker="فاروقی اے آئی نیوز", h="اے آئی کی دنیا: آج کی اہم خبریں", date=date)
    if tl.get("tune"):                                   # دھن کے دوران «آج کی شہ سرخیاں»
        scene(tl["tune"][0], "bridge", h="آج کی شہ سرخیاں")
    for hc in tl["hcards"]:
        s = sts[hc["i"]]
        scene(hc["t0"] - 0.3, "headline", num=f"سرخی  {hc['i'] + 1}", h=s["headline"],
              logo=s.get("_logo"), co=s.get("company") or "")
    if tl["stories"]:
        bridge_t = max(tl["hcards"][-1]["t1"] if tl["hcards"] else 0, 0)
        scene(bridge_t, "bridge", h="تفصیل")
    for i, (st, s) in enumerate(zip(tl["stories"], sts)):
        q = br.query_for(s)
        scene(st["t0"], "headline", num=f"خبر  {i + 1}", h=s.get("screen") or s["headline"],
              logo=s.get("_logo"), co=s.get("company") or "")
        mine = [u for u in utt if st["t0"] <= u["t0"] < st["t1"]]
        anchors_seen = 0
        for u in mine:
            if u["kind"] == "vo":
                scene(u["t0"] - 0.2, "points", pts=(s.get("points") or [])[:3] or [s["headline"]], shot=s.get("_shot"))
            elif u["kind"] == "reporter":
                scene(u["t0"] - 0.2, "broll", "city night aerial", chip=f"⌖ {s.get('location') or ''}  ·  رپورٹ: زید")
            else:
                anchors_seen += 1
                if anchors_seen == 1:                      # تمہید: اصل ویب سائٹ، ورنہ متعلقہ ویڈیو
                    if s.get("_shot"):
                        scene(u["t0"] - 0.2, "site", q, shot=s["_shot"], url=(s.get("domain") or ""), pan=500)
                    else:
                        scene(u["t0"] - 0.2, "broll", q, chip=s.get("company") or "")
                elif s.get("reporter") and anchors_seen == 2:  # نامہ نگار کو لینا
                    scene(u["t0"] - 0.2, "loc", loc=s.get("location") or "", who="رپورٹ: زید")
                else:
                    scene(u["t0"] - 0.2, "broll", q)
    scenes.sort(key=lambda x: x["t0"])
    for a, b in zip(scenes, scenes[1:]):
        a["t1"] = b["t0"]
    scenes[-1]["t1"] = tl["dur"] + 0.1
    caps = [c for u in utt for c in _chunks(u["text"], u["t0"], u["t1"])]
    segs.sort()
    ranges = [(a[0], b[0], a[1]) for a, b in zip(segs, segs[1:])] + [(segs[-1][0], tl["dur"], segs[-1][1])]
    return scenes, caps, [r for r in ranges if r[1] - r[0] > 0.05]


def _track(ranges: list, dest: Path, tmp: Path) -> Path | None:
    parts, used = [], {}
    for i, (a, b, q) in enumerate(ranges):
        clips = br.fetch(q, dest) or br.fetch(br.GENERIC, dest)
        if not clips:
            return None
        left, k = b - a, 0
        while left > 0.05:
            c = clips[(used.get(q, 0) + k) % len(clips)]
            ln = min(6.0, left)
            p = tmp / f"xb_{i:03d}_{k:02d}.mp4"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", str(c), "-t", f"{ln:.3f}", "-an",
                            "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=25,setsar=1,"
                                   "eq=brightness=-0.05:saturation=0.85",
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(p)], check=True)
            parts.append(p)
            left -= ln
            k += 1
        used[q] = used.get(q, 0) + k
    lst = tmp / "xbroll.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    out = tmp / "xbroll.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)], check=True)
    return out


def render(d: dict, tl: dict, audio: Path, out: Path, tmp: Path, date: str, launch, font: Path, logo_b64: str) -> Path:
    from playwright.sync_api import sync_playwright
    scenes, caps, ranges = plan(d, tl, date)
    track = _track(ranges, Path(os.environ.get("BROLL_DIR") or (ROOT / "cache" / "broll")), tmp)
    keep_key = not track and os.environ.get("FORCE_KEY") == "1"      # نمونہ: میجنٹا رہنے دیں (ویڈیو بعد میں)
    if keep_key:
        (out.parent / "ranges.json").write_text(json.dumps(ranges), encoding="utf-8")
    html = (A / "explainer.html").read_text(encoding="utf-8")
    html = (html.replace("__NQFONT__", font.as_uri()).replace("__LOGO__", logo_b64)
            .replace("__NFDATA__", json.dumps({"scenes": scenes, "caps": caps}, ensure_ascii=False)))
    if not track and not keep_key:                        # ویڈیو نہ ملے: میجنٹا کی جگہ گہرا نیلا
        html = html.replace("background:#ff00ff", "background:#0a1544")
    p = tmp / "explainer_built.html"
    p.write_text(html, encoding="utf-8")
    silent = tmp / "x_silent.mp4"
    enc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "8" if (track or keep_key) else "20",
           "-pix_fmt", "yuv444p" if (track or keep_key) else "yuv420p"]
    with sync_playwright() as pw:
        b = launch(pw)
        pg = b.new_page(viewport={"width": 1920, "height": 1080})
        pg.goto(p.as_uri())
        pg.wait_for_function("document.title==='ready'", timeout=90000)
        ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg",
                               "-i", "-", *enc, str(silent)], stdin=subprocess.PIPE)
        n = int(tl["dur"] * FPS)
        for f in range(n):
            pg.evaluate(f"render({f / FPS})")
            ff.stdin.write(pg.screenshot(type="jpeg", quality=97 if (track or keep_key) else 88))
            if f % (FPS * 30) == 0:
                print(f"   فریم {f}/{n}")
        ff.stdin.close()
        ff.wait()
        b.close()
    if track:
        silent = br.composite(silent, track, tmp / "x_keyed.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(audio), "-c:v", "copy", "-c:a", "aac",
                    "-b:a", "192k", "-shortest", str(out)], check=True)
    return out
