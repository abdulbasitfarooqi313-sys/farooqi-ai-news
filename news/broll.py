"""بغیر اینکر (faceless) بلیٹن کے لیے خبر سے متعلق ویڈیو مناظر — Pexels (مفت، کمرشل اجازت، حوالہ ضروری نہیں)۔

اسٹوڈیو والا حصہ (اور نامہ نگار کا خانہ) صفحے پر میجنٹا (#ff00ff) رنگ سے بنتا ہے؛ یہاں اسی جگہ ffmpeg سے
پیچھے متعلقہ ویڈیو لگتی ہے۔ چابی: PEXELS_API_KEY (GitHub Secret)۔ نہ ہو یا BROLL_DIR میں فائلیں نہ ہوں تو
خالی اسٹوڈیو (لوگو والی اسکرین) لگتا ہے۔
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import requests

TOPIC_QUERY = {
    "security": "cyber security hacker code", "data": "data center servers", "law": "courtroom justice",
    "ai": "artificial intelligence technology", "robot": "robot technology", "chip": "computer chip semiconductor",
    "money": "stock market finance", "health": "medical technology hospital", "car": "self driving car",
    "phone": "smartphone app", "education": "students laptop classroom", "jobs": "office workers computer",
    "energy": "power plant electricity", "space": "satellite earth space", "music": "music studio",
    "video": "video editing screen", "search": "internet search laptop", "social": "social media phone",
}
GENERIC = "artificial intelligence technology"
KEY = "ff00ff"


def slug(q: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", q.lower()).strip("-")[:40]


def query_for(story: dict) -> str:
    t = (story.get("topic") or "").lower().strip()
    return TOPIC_QUERY.get(t) or (f"{t} technology" if t else GENERIC)


def fetch(query: str, dest: Path, n: int = 3) -> list[Path]:
    """Pexels سے n افقی ویڈیوز (HD) — پہلے سے موجود ہوں تو وہی"""
    d = dest / slug(query)
    have = sorted(d.glob("*.mp4"))
    if have:
        return have
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        return []
    r = requests.get("https://api.pexels.com/videos/search", headers={"Authorization": key}, timeout=30,
                     params={"query": query, "orientation": "landscape", "size": "medium", "per_page": 12})
    if not r.ok:
        print(f"   pexels {r.status_code}: {query}")
        return []
    d.mkdir(parents=True, exist_ok=True)
    out = []
    for v in r.json().get("videos", []):
        if v.get("duration", 0) < 5:
            continue
        files = sorted((f for f in v.get("video_files", []) if f.get("file_type") == "video/mp4" and 1200 <= (f.get("width") or 0) <= 1920),
                       key=lambda f: -f["width"])
        if not files:
            continue
        p = d / f"{v['id']}.mp4"
        try:
            p.write_bytes(requests.get(files[0]["link"], timeout=120).content)
            out.append(p)
        except requests.RequestException:
            continue
        if len(out) >= n:
            break
    return out


def segments(d: dict, tl: dict) -> list[tuple[float, float, str]]:
    """(شروع، آخر، تلاش) — آغاز/سرخیاں: عمومی اے آئی، ہر خبر: اس کا موضوع"""
    segs, t = [], 0.0
    for st, s in zip(tl["stories"], d["stories"]):
        if st["t0"] > t:
            segs.append((t, st["t0"], GENERIC))
        segs.append((st["t0"], st["t1"], query_for(s)))
        t = st["t1"]
    if tl["dur"] > t:
        segs.append((t, tl["dur"], GENERIC))
    return segs


def track(d: dict, tl: dict, dest: Path, tmp: Path) -> Path | None:
    """پورے بلیٹن کی لمبائی کا پسِ منظر ویڈیو ٹریک (1920×1080، بغیر آواز) — ہر کلپ زیادہ سے زیادہ 6 سیکنڈ"""
    parts, used = [], {}
    for i, (a, b, q) in enumerate(segments(d, tl)):
        clips = fetch(q, dest) or fetch(GENERIC, dest)
        if not clips:
            return None
        left, k = b - a, 0
        while left > 0.05:
            c = clips[(used.get(q, 0) + k) % len(clips)]
            ln = min(6.0, left)
            p = tmp / f"br_{i:02d}_{k:02d}.mp4"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", str(c), "-t", f"{ln:.3f}", "-an",
                            "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=25,setsar=1,"
                                   "eq=brightness=-0.04:saturation=0.9",
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(p)], check=True)
            parts.append(p)
            left -= ln
            k += 1
        used[q] = used.get(q, 0) + k
    lst = tmp / "broll.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    out = tmp / "broll.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)], check=True)
    return out


def composite(body_silent: Path, broll: Path, out: Path) -> Path:
    """میجنٹا جگہوں پر پیچھے کی ویڈیو"""
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(broll), "-i", str(body_silent), "-filter_complex",
                    f"[1]format=yuv444p,colorkey=0x{KEY}:0.32:0.08[fg];[0][fg]overlay=shortest=1,format=yuv420p",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(out)], check=True)
    return out
