"""⚡ اے آئی فلیش — کھڑی (9:16) ریپڈ فائر سرخیاں: 15 تا 20 خبریں، مختلف ملکوں سے، ہر ایک آواز میں (یوٹیوب شارٹ)۔

انداز (مالک کا نمونہ): اوپر سرخ تیر والی پٹی «تازہ خبر ۰۱»، پوری اسکرین پر خبر کے موضوع کی تصویر (Pexels — مفت،
کمرشل اجازت)، بیچ میں پیلے خانے میں اردو سرخی (ٹکڑوں میں بنتا خانہ)، ملک کا نام، کمپنی کا لوگو؛ آخر میں «دیکھنے کا شکریہ»۔
انگریزی میں کچھ نہیں لکھا جاتا۔ دن: اتوار، منگل، جمعرات (شام 5 بجے، ✅ کے بعد)۔

آواز: FLASH_TTS=gemini (طے شدہ) یا edge (مائیکروسافٹ کی مفت اردو آواز — نمونے کے لیے)۔
python -m news.flash            → آج کی فلیش (اگر آج کا دن ہو اور نہ بنی ہو)
python -m news.flash force      → ابھی بنائیں
python -m news.flash sample     → صرف ویڈیو بنا کر flash.mp4 (ٹیلیگرام/یوٹیوب نہیں)
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import requests

from . import bulletin as B
from .base import generate_json, read_json, write_json, send_text

FLASH_DAYS = {6, 1, 3}             # اتوار، منگل، جمعرات (پیر/بدھ/ہفتہ = بلیٹن، جمعہ = پوڈکاسٹ) — مالک کی منظور شدہ تقسیم
TTS_NEED = 4                       # آغاز + 2 بلاک + اختتام
FPS = 25
MIN_N, MAX_N = 15, 20
GN = "https://news.google.com/rss/search?q=%22artificial+intelligence%22+OR+AI+when:2d&hl={hl}&gl={gl}&ceid={gl}:{lang}"
EDITIONS = [("en-US", "US", "en"), ("en-GB", "GB", "en"), ("en-IN", "IN", "en"), ("en-PK", "PK", "en"), ("en-AU", "AU", "en"),
            ("en-CA", "CA", "en"), ("en-SG", "SG", "en"), ("en-ZA", "ZA", "en"), ("en-NG", "NG", "en"), ("en-AE", "AE", "en")]
FEEDS = [GN.format(hl=h, gl=g, lang=l) for h, g, l in EDITIONS] + [
    "https://news.google.com/rss/search?q=AI+China+OR+Japan+OR+Korea+OR+Europe+OR+Saudi+when:2d&hl=en-US&gl=US&ceid=US:en"]

SYSTEM = """آپ «فاروقی اے آئی نیوز» کے اردو نیوز پروڈیوسر ہیں۔ پروگرام: «اے آئی فلیش» — یوٹیوب شارٹ میں تیز رفتار سرخیاں، صرف سرخی، کوئی تفصیل نہیں۔
دی گئی خبروں میں سے 18 مختلف خبریں چنیں جن کا **مرکز مصنوعی ذہانت (AI)** ہو — جس خبر میں AI صرف ضمنی ذکر ہو (عام کاروبار، جائیداد، اسٹاک مارکیٹ، جرائم) وہ نہیں — جتنے زیادہ مختلف ملک ہو سکیں (امریکہ، چین، برطانیہ، یورپ، بھارت، پاکستان، خلیج، جاپان، کوریا، افریقہ…)؛ ایک ہی ملک کی تین سے زیادہ نہیں۔
سختی سے: صرف دی گئی خبروں کے حقائق؛ کوئی عدد، نام یا دعویٰ اپنی طرف سے نہیں۔ ایک واقعے کی دو سرخیاں نہیں۔ سیاسی رائے، سنسنی اور سرمایہ کاری کا مشورہ نہیں۔
سرخی: خبر والا مکمل جملہ، 7 تا 12 الفاظ، سادہ اردو؛ انگریزی نام اردو رسم الخط میں (OpenAI = اوپن اے آئی، Google = گوگل، Nvidia = این ویڈیا)۔ کوئی انگریزی حرف، ایموجی، بریکٹ نہیں۔
صرف JSON:
{"items": [{"h": "سرخی", "country": "ملک کا نام اردو میں (مثلاً جاپان، برطانیہ، عالمی)", "photo_query": "Pexels تصویر کی تلاش، انگریزی 2 تا 4 الفاظ (موضوع کا منظر؛ کسی شخص یا برانڈ کا نام نہیں)",
            "company": "مرکزی کمپنی کا انگریزی نام یا خالی", "domain": "سرکاری ڈومین یا خالی", "n": "فہرست میں خبر کا نمبر"}],
 "open_sub": "آغاز کی ذیلی سطر، 3 تا 6 الفاظ (مثلاً «دنیا بھر سے اٹھارہ خبریں»)",
 "youtube_title": "شارٹ کا عنوان (زیادہ سے زیادہ 80 حروف، اردو)", "summary": "تفصیل کا 1 تا 2 جملے", "tags": ["10 تا 15 ٹیگ اردو/انگریزی"]}"""


def script(items: list[dict], feedback: str | None = None) -> dict:
    listing = "\n".join(f"[{i + 1}] {it['title']} — {it['source']} · {it['summary'][:160]}" for i, it in enumerate(items[:180]))
    user = f"آج: {B.urdu_date()}\n\nپچھلے دو دن کی AI خبریں (مختلف ملکی ایڈیشن):\n{listing}"
    if feedback:
        user += f"\n\nمالک کی ہدایت: {feedback}"
    d = generate_json(SYSTEM, user)
    seen, out = set(), []
    for h in d.get("items", []):
        t = re.sub(r"[A-Za-z]", "", (h.get("h") or "")).strip()
        k = re.sub(r"\W+", "", t)[:30]
        if t and k not in seen:
            seen.add(k)
            h["h"] = t
            try:
                it = items[int(str(h.get("n", "")).strip()) - 1]
                h["source"], h["link"] = it["source"], it["link"]
            except (ValueError, IndexError):
                pass
            out.append(h)
    d["items"] = out[:MAX_N]
    if len(d["items"]) < MIN_N:
        raise RuntimeError(f"فلیش کے لیے کافی سرخیاں نہیں ({len(d['items'])})")
    return d


def photo(query: str, dest: Path, used: set) -> str | None:
    """Pexels کی کھڑی تصویر (ہر خبر کی الگ) → data URI"""
    key = os.environ.get("PEXELS_API_KEY")
    if not key or not query:
        return None
    try:
        r = requests.get("https://api.pexels.com/v1/search", headers={"Authorization": key}, timeout=30,
                         params={"query": query, "orientation": "portrait", "per_page": 15, "size": "large"})
        for ph in r.json().get("photos", []):
            if ph["id"] in used:
                continue
            used.add(ph["id"])
            img = requests.get(ph["src"]["large2x"], timeout=60).content
            dest.write_bytes(img)
            return B._b64(dest, "image/jpeg")
    except Exception as e:
        print(f"   تصویر نہیں ملی ({query}): {e}")
    return None


def photo_pixabay(query: str, dest: Path, used: set) -> str | None:
    """Pixabay (مفت، کمرشل اجازت، حوالہ ضروری نہیں) — PIXABAY_API_KEY؛ Pexels نہ ہو تو"""
    key = os.environ.get("PIXABAY_API_KEY")
    if not key or not query:
        return None
    try:
        r = requests.get("https://pixabay.com/api/", timeout=30, params={"key": key, "q": query, "image_type": "photo",
                         "orientation": "vertical", "safesearch": "true", "per_page": 20, "min_height": 1600})
        for ph in r.json().get("hits", []):
            if ("pb", ph["id"]) in used:
                continue
            used.add(("pb", ph["id"]))
            dest.write_bytes(requests.get(ph.get("largeImageURL") or ph["webformatURL"], timeout=60).content)
            return B._b64(dest, "image/jpeg")
    except Exception as e:
        print(f"   Pixabay تصویر نہیں ملی ({query}): {e}")
    return None


def _edge(texts: list[str], tmp: Path) -> list[Path]:
    import edge_tts
    out = []
    for i, t in enumerate(texts):
        mp3 = tmp / f"fe{i}.mp3"
        for k in range(3):
            try:
                asyncio.run(edge_tts.Communicate(t, "ur-PK-UzmaNeural", rate="+6%").save(str(mp3)))
                break
            except Exception:
                import time
                time.sleep(4 * (k + 1))
        out.append(B._norm(mp3, tmp / f"fe{i}.wav", pad=0.1))
    return out


def voices(texts: list[str], tmp: Path) -> list[Path]:
    if os.environ.get("FLASH_TTS", "gemini") == "edge":
        return _edge(texts, tmp)
    # جیمنائی: 10 سرخیاں ایک درخواست میں، پھر کاٹ کر
    from .base import _split, SplitError
    head, rest, tail = texts[0], texts[1:-1], texts[-1]
    blocks = [rest[i:i + 10] for i in range(0, len(rest), 10)]
    wavs = B._speak([head] + ["\n\n".join(b) for b in blocks] + [tail], B.ANCHOR_VOICE, tmp, "fl")
    out = [wavs[0]]
    for j, (b, w) in enumerate(zip(blocks, wavs[1:-1])):
        try:
            out += _split(w, b, tmp, f"fb{j}")
        except SplitError:
            from .base import _cut
            tot = B._dur(w)
            wts = [len(x) + 12 for x in b]
            cuts, acc = [], 0
            for x in wts[:-1]:
                acc += x
                cuts.append(tot * acc / sum(wts))
            out += _cut(w, cuts, tot, len(b), tmp, f"fb{j}")
    return out + [wavs[-1]]


def build(d: dict, tmp: Path) -> tuple[Path, Path]:
    n = len(d["items"])
    opening = (f"السلام علیکم! فاروقی اے آئی نیوز کی اے آئی فلیش میں خوش آمدید۔ "
               f"{d.get('open_sub') or 'دنیا بھر سے مصنوعی ذہانت کی تازہ خبریں'}۔")
    closing = "یہ تھیں آج کی اہم خبریں۔ ہمارے چینل کو سبسکرائب کیجیے، اور مزید خبروں کے لیے ہمارے ساتھ جڑے رہیے۔ اللہ حافظ۔"
    ws = voices([opening] + [it["h"] for it in d["items"]] + [closing], tmp)
    ws = [B._trim(w, tmp / f"ft{i}.wav") for i, w in enumerate(ws)]
    parts, t = [], 0.0

    def add(p: Path):
        nonlocal t
        parts.append(p)
        t0, t = t, t + B._dur(p)
        return t0, t

    add(B._sil(0.3, tmp / "fs0.wav"))
    add(ws[0])
    open_end = t + 0.15
    whoosh = tmp / "whoosh.wav"
    B._ff("-i", str(B.A / "sting.wav"), "-t", "0.45", "-af", "volume=0.5,afade=t=out:st=0.2:d=0.25", "-ar", "44100", "-ac", "2",
          "-c:a", "pcm_s16le", str(whoosh))
    for i, w in enumerate(ws[1:-1]):
        a0, _ = add(whoosh)
        add(w)
        _, b1 = add(B._sil(0.35, tmp / f"fg{i}.wav"))
        d["items"][i]["t0"], d["items"][i]["t1"] = round(a0, 2), round(b1, 2)
    end_t = t
    add(B._sil(0.2, tmp / "fend0.wav"))
    add(ws[-1])
    add(B._sil(1.2, tmp / "fend.wav"))
    lst = tmp / "flist.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    voice = tmp / "fvoice.wav"
    B._ff("-f", "concat", "-safe", "0", "-i", str(lst), "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(voice))
    dur = B._dur(voice)
    audio = tmp / "faudio.wav"
    B._ff("-i", str(voice), "-stream_loop", "-1", "-i", str(B.A / "hbed.wav"), "-filter_complex",
          f"[1]volume=0.22,afade=t=in:d=0.5,afade=t=out:st={dur - 2:.2f}:d=2[b];"
          "[0][b]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5[a]",
          "-map", "[a]", "-t", f"{dur:.2f}", "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(audio))
    data = {"items": [{k: it.get(k) for k in ("h", "country", "t0", "t1")} | {"photo": it.get("_photo"), "logo": it.get("_logo")}
                      for it in d["items"]],
            "open_end": round(open_end, 2), "open_sub": d.get("open_sub") or f"دنیا بھر سے {n} خبریں",
            "open_photo": d["items"][0].get("_photo"), "end_t": round(end_t, 2), "dur": round(dur, 2)}
    html = (B.A / "flash.html").read_text(encoding="utf-8")
    html = (html.replace("__NQFONT__", B.FONT.as_uri()).replace("__LOGO__", B._b64(B.A / "logo_round.png", "image/png"))
            .replace("__NFDATA__", json.dumps(data, ensure_ascii=False)))
    page = tmp / "flash_built.html"
    page.write_text(html, encoding="utf-8")
    silent = tmp / "flash_silent.mp4"
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        br = B._launch(pw)
        pg = br.new_page(viewport={"width": 1080, "height": 1920})
        pg.goto(page.as_uri())
        pg.wait_for_function("document.title==='ready'", timeout=90000)
        ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg", "-i", "-",
                               "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(silent)], stdin=subprocess.PIPE)
        nf = int(dur * FPS)
        for f in range(nf):
            pg.evaluate(f"render({f / FPS})")
            ff.stdin.write(pg.screenshot(type="jpeg", quality=88))
            if f % (FPS * 20) == 0:
                print(f"   فریم {f}/{nf}")
        ff.stdin.close()
        ff.wait()
        br.close()
    out = tmp / "flash.mp4"
    B._ff("-i", str(silent), "-i", str(audio), "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out))
    thumb = tmp / "flash_thumb.jpg"
    B._ff("-ss", str(d["items"][0]["t0"] + 1.2), "-i", str(out), "-frames:v", "1", "-q:v", "2", str(thumb))
    return out, thumb


def make(sample: bool = False, feedback: str | None = None) -> Path:
    if os.environ.get("FLASH_TTS", "gemini") == "gemini":
        B.tts_guard(TTS_NEED, "اے آئی فلیش")
    items = B.fetch(max_age_h=48, feeds=FEEDS, per_feed=30)
    if len(items) < 30:
        raise RuntimeError(f"کافی خبریں نہیں ملیں ({len(items)})")
    d = script(items, feedback)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        used: set = set()
        for i, it in enumerate(d["items"]):
            q = it.get("photo_query") or "artificial intelligence technology"
            it["_photo"] = photo(q, tmp / f"p{i}.jpg", used) or photo_pixabay(q, tmp / f"p{i}.jpg", used)
            it["_logo"] = B._logo(it.get("domain") or "", tmp, i)
        out, thumb = build(d, tmp)
        final = B.ROOT / "flash.mp4"
        import shutil
        shutil.copy(out, final)
        shutil.copy(thumb, B.ROOT / "flash_thumb.jpg")
        write_json(B.ROOT / "state" / "flash_last.json", {k: v for k, v in d.items() if k != "items"} |
                   {"items": [{k: v for k, v in it.items() if not k.startswith("_")} for it in d["items"]]})
        if sample:
            print(f"✅ نمونہ: {len(d['items'])} سرخیاں، {B._dur(final):.0f}s")
            return final
        n = len(d["items"])
        sd = {"youtube_title": (d.get("youtube_title") or f"اے آئی فلیش: دنیا بھر سے {n} خبریں")[:90] + " #shorts",
              "youtube_description": (d.get("summary", "") + "\n\n" + "\n".join(f"{i + 1}. {it['h']}" for i, it in enumerate(d["items"]))
                                      + "\n\n🎬 Photos: Pexels / Pixabay\nآواز: اے آئی\n\n#shorts #اے_آئی #AINews #فاروقی_اے_آئی_نیوز")[:4900],
              "tags": list(dict.fromkeys((d.get("tags") or []) + ["اے آئی فلیش", "AI News Urdu", "فاروقی اے آئی نیوز", "shorts"]))}
        key = B._today() + "-f"
        d["stories"] = [{"headline": it["h"]} for it in d["items"]]
        vmid, mids = B.deliver(final, B.ROOT / "flash_thumb.jpg", sd, d, key=key, label=f"اے آئی فلیش — {n} سرخیاں", size=(1080, 1920))
        ytinfo = B._yt_upload(final, None, sd)
    st = read_json(B.STATE) if B.STATE.exists() else {}
    st.setdefault("days", {})[key] = {"status": "pending", "vmid": vmid, "mids": mids, "kind": "flash", **ytinfo}
    st.pop("redo_f", None)
    st["days"] = dict(sorted(st["days"].items())[-60:])
    write_json(B.STATE, st)
    return final


def tick(force: bool = False) -> None:
    st = read_json(B.STATE) if B.STATE.exists() else {}
    redo = st.get("redo_f")
    if redo:
        make(feedback=redo.get("feedback") if isinstance(redo, dict) else None)
        return
    if not force and dt.datetime.now(B.TZ).weekday() not in FLASH_DAYS:
        print("آج فلیش کا دن نہیں (بلیٹن والا دن)")
        return
    if not force and (B._today() + "-f") in st.get("days", {}):
        print("آج کی فلیش بن چکی")
        return
    make()


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "sample":
        make(sample=True)
        sys.exit(0)
    try:
        tick(force=arg == "force")
    except Exception as e:
        try:
            send_text(B.news_chat(), f"⚠️ آج کی «اے آئی فلیش» نہ بن سکی: {str(e)[:250]}", html=False)
        except Exception:
            pass
        raise
