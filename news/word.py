"""📘 «آج کا اے آئی لفظ» — روزانہ 30–45 سیکنڈ کا کھڑا شارٹ: اے آئی کی ایک اصطلاح، آسان اردو تعریف، روزمرہ مثال۔

صرف ریزرو (دوسری) جیمنائی چابی کی بچت سے، رات 9 بجے (`news/reserve.py`)۔ ایک ہی آواز کی درخواست (کبھی دو)۔
ٹیلیگرام ✅/❌ (کلید `YYYY-MM-DD-w`) + یوٹیوب Private → ✅ پر اگلے دن دوپہر 1 بجے سعودی (3 بجے پاکستان)۔
جیمنائی آواز نہ بنے تو اس رات کچھ نہیں بنتا (مالک کا اصول: اصل ویڈیو = جیمنائی؛ نمونہ = مائیکروسافٹ)۔

python -m news.word sample   → صرف word.mp4، مائیکروسافٹ آواز (ٹیلیگرام/یوٹیوب نہیں)
"""
from __future__ import annotations

import asyncio
import base64
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

import requests

from . import bulletin as B
from . import flash as F
from .base import generate_json, read_json, write_json, send_text, _norm
from .explainer import _chunks

PLAYLIST = "آج کا اے آئی لفظ"
VOICE = B.ANCHOR_VOICE                 # بلیٹن والی میزبان کی آواز — چینل کی پہچان
USED = B.ROOT / "state" / "words_used.json"
TTS_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent"
FPS = B.FPS

SYSTEM = """آپ «فاروقی اے آئی نیوز» کے روزانہ شارٹ «آج کا اے آئی لفظ» کے لکھاری ہیں۔ ناظر: عام پاکستانی — طالب علم، نوجوان، والدین، دکاندار۔
مصنوعی ذہانت کی **ایک** اصطلاح چنیں جو پہلے استعمال شدہ فہرست میں نہ ہو؛ اگر آج کی خبروں میں کوئی اصطلاح نمایاں ہو تو وہ بہتر، ورنہ بنیادی سے شروع کر کے بتدریج (چیٹ بوٹ، پرامپٹ، ڈیپ فیک، مشین لرننگ…)۔
اسکرپٹ (بولا جانے والا، 75 تا 100 الفاظ، تقریباً 35–45 سیکنڈ): «السلام علیکم! آج کا اے آئی لفظ ہے: …» ← ایک جملے میں آسان تعریف ← پاکستان کی روزمرہ زندگی سے ایک مثال
← ایک احتیاط یا کام کی بات ← «ایسے ہی آسان اسباق کے لیے چینل کو سبسکرائب کیجیے۔ اللہ حافظ۔»
سختی سے: درست، مستند معلومات؛ کوئی عدد/دعویٰ گھڑنا نہیں؛ انگریزی اصطلاح اردو رسم الخط میں (Prompt = پرامپٹ)؛ کوئی انگریزی حرف، ایموجی، بریکٹ نہیں۔
صرف JSON: {"term": "اصطلاح اردو رسم الخط میں (1 تا 3 الفاظ)", "en": "English term", "script": "بولا جانے والا متن",
 "meaning": "اسکرین پر: ایک مختصر جملے کی تعریف (8 تا 14 الفاظ)", "example": "اسکرین پر: مختصر مثال (8 تا 14 الفاظ)",
 "photo_query": "Pixabay تصویر کی تلاش، انگریزی 2 تا 4 الفاظ — صرف اشیا/ٹیکنالوجی کا منظر (کمپیوٹر، سرکٹ، روبوٹ، فون…)، کوئی انسان، چہرہ یا برانڈ نہیں",
 "youtube_title": "عنوان (اردو، زیادہ سے زیادہ 70 حروف)", "summary": "تفصیل کے 1 تا 2 جملے", "tags": ["10 تا 14 ٹیگ اردو/انگریزی"]}"""


def script(feedback: str | None = None) -> dict:
    used = read_json(USED) if USED.exists() else []
    try:
        heads = "\n".join(f"- {it['title']}" for it in B.fetch(max_age_h=36)[:40])
    except Exception:
        heads = ""
    user = (f"پہلے استعمال شدہ اصطلاحات (دوبارہ نہیں): {', '.join(u['en'] for u in used) or 'کوئی نہیں'}\n\n"
            f"آج کی اے آئی سرخیاں (اصطلاح چننے میں مدد کے لیے):\n{heads}")
    if feedback:
        user += f"\n\nمالک کی ہدایت: {feedback}"
    d = generate_json(SYSTEM, user)
    for k in ("term", "script", "meaning", "example"):
        d[k] = re.sub(r"[A-Za-z]", "", d.get(k) or "").strip()
        if not d[k]:
            raise RuntimeError(f"اسکرپٹ نامکمل ({k})")
    d["n"] = len(used) + 1
    return d


def _gem_voice(text: str, dest: Path) -> Path | None:
    """صرف ریزرو چابی؛ OTHER پر ایک بار دوبارہ"""
    key = os.environ.get("GEMINI_BACKUP_KEY", "").strip()
    if not key:
        return None
    for attempt in range(2):
        r = requests.post(TTS_URL, params={"key": key}, timeout=240, json={
            "contents": [{"parts": [{"text": "Read the following Urdu text aloud in a clear, friendly, energetic tone:\n\n" + text}]}],
            "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {
                "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": VOICE}}}}})
        B.tts_note_backup()
        c = (r.json().get("candidates") or [{}])[0] if r.ok else {}
        if c.get("content"):
            part = c["content"]["parts"][0]["inlineData"]
            rate = int(re.search(r"rate=(\d+)", part.get("mimeType", "rate=24000")).group(1))
            raw = dest.with_suffix(".raw.wav")
            with wave.open(str(raw), "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(base64.b64decode(part["data"]))
            return _norm(raw, dest, pad=0.1)
        print("TTS", r.status_code, c.get("finishReason"), r.text[:160].replace("\n", " "))
        if r.status_code == 429:
            return None
        time.sleep(8)
    return None


def _edge_voice(text: str, dest: Path) -> Path:
    import edge_tts
    mp3 = dest.with_suffix(".mp3")
    asyncio.run(edge_tts.Communicate(text, "ur-PK-UzmaNeural", rate="+4%").save(str(mp3)))
    return _norm(mp3, dest, pad=0.1)


NO_PEOPLE = ("woman", "man", "girl", "boy", "person", "people", "child", "face", "female", "male", "lady", "portrait", "human",
             "businessman", "businesswoman", "student", "kid", "hand", "hands", "model", "selfie")


def _photo_no_people(q: str, dest: Path) -> str | None:
    """Pixabay کی کھڑی تصویر جس کے ٹیگ میں کوئی انسان نہ ہو (مالک: تصاویر میں چہرے نہیں)"""
    key = os.environ.get("PIXABAY_API_KEY", "").strip()
    if not key:
        return None
    try:
        r = requests.get("https://pixabay.com/api/", timeout=30, params={"key": key, "q": q, "image_type": "photo",
                         "orientation": "vertical", "safesearch": "true", "per_page": 40, "min_height": 1600})
        for h in r.json().get("hits", []):
            tags = (h.get("tags") or "").lower()
            if any(re.search(rf"\b{b}\b", tags) for b in NO_PEOPLE):
                continue
            dest.write_bytes(requests.get(h.get("largeImageURL") or h["webformatURL"], timeout=60).content)
            return B._b64(dest, "image/jpeg")
    except Exception as e:
        print("تصویر نہیں ملی:", e)
    return None


def build(d: dict, voice: Path, tmp: Path) -> tuple[Path, Path]:
    voice = B._trim(voice, tmp / "v.trim.wav")
    vd = B._dur(voice)
    lead, tail = 0.8, 3.2
    full = tmp / "full.wav"
    B._ff("-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={lead}", "-i", str(voice), "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={tail}",
          "-filter_complex", "[1]aformat=sample_rates=44100:channel_layouts=stereo[v];[0][v][2]concat=n=3:v=0:a=1[a]", "-map", "[a]",
          "-c:a", "pcm_s16le", str(full))
    dur = B._dur(full)
    audio = tmp / "audio.wav"
    B._ff("-i", str(full), "-stream_loop", "-1", "-i", str(B.A / "hbed.wav"), "-filter_complex",
          f"[1]volume=0.16,afade=t=in:d=0.6,afade=t=out:st={dur - 2:.2f}:d=2[b];"
          "[0][b]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5[a]",
          "-map", "[a]", "-t", f"{dur:.2f}", "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(audio))
    caps = _chunks(d["script"], lead, lead + vd, max_words=6)
    used: set = set()
    q = d.get("photo_query") or "artificial intelligence technology"
    photo = _photo_no_people(q, tmp / "p.jpg") or _photo_no_people("artificial intelligence technology abstract", tmp / "p.jpg") or ""
    data = {"term": d["term"], "n": d["n"], "meaning": d["meaning"], "example": d["example"], "caps": caps, "photo": photo,
            "t_meaning": round(lead + vd * 0.22, 2), "t_example": round(lead + vd * 0.5, 2), "end_t": round(lead + vd + 0.3, 2), "dur": round(dur, 2)}
    html = (B.A / "word.html").read_text(encoding="utf-8")
    html = (html.replace("__NQFONT__", B.FONT.as_uri()).replace("__LOGO__", B._b64(B.A / "logo_round.png", "image/png"))
            .replace("__NFDATA__", json.dumps(data, ensure_ascii=False)))
    page = tmp / "w.html"
    page.write_text(html, encoding="utf-8")
    silent, thumb = tmp / "silent.mp4", tmp / "thumb.jpg"
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        br = B._launch(pw)
        pg = br.new_page(viewport={"width": 1080, "height": 1920})
        pg.goto(page.as_uri())
        pg.wait_for_function("document.title==='ready'", timeout=90000)
        ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg", "-i", "-",
                               "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(silent)], stdin=subprocess.PIPE)
        for f in range(int(dur * FPS)):
            pg.evaluate(f"render({f / FPS})")
            ff.stdin.write(pg.screenshot(type="jpeg", quality=88))
        ff.stdin.close()
        ff.wait()
        pg.evaluate(f"render({data['t_example'] + 1.5})")
        pg.screenshot(path=str(thumb), type="jpeg", quality=90)
        br.close()
    out = tmp / "word.mp4"
    B._ff("-i", str(silent), "-i", str(audio), "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out))
    return out, thumb


def make(sample: bool = False, feedback: str | None = None) -> bool:
    d = script(feedback)
    print("لفظ:", d["term"], "/", d.get("en"))
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        voice = _edge_voice(d["script"], tmp / "v.wav") if sample else _gem_voice(d["script"], tmp / "v.wav")
        if not voice:
            print("جیمنائی آواز نہیں بنی — آج «اے آئی لفظ» نہیں (اصل ویڈیو صرف جیمنائی آواز سے)")
            return False
        out, thumb = build(d, voice, tmp)
        shutil.copy(out, B.ROOT / "word.mp4")
        shutil.copy(thumb, B.ROOT / "word_thumb.jpg")
    final = B.ROOT / "word.mp4"
    print(f"✅ لفظ کا شارٹ: {B._dur(final):.0f}s")
    if sample:
        return True
    now = dt.datetime.now(B.TZ)
    when = (now + dt.timedelta(days=1)).replace(hour=13, minute=0, second=0, microsecond=0)   # اگلے دن 1 بجے سعودی (3 بجے پاکستان)
    sd = {"youtube_title": (d.get("youtube_title") or f"{d['term']} کیا ہے؟ آج کا اے آئی لفظ")[:85] + " #shorts",
          "youtube_description": (f"📘 آج کا اے آئی لفظ ({d['n']}): {d['term']}\n\n{d['meaning']}\n\nمثال: {d['example']}\n\n{d.get('summary', '')}\n\n"
                                  "ہر روز مصنوعی ذہانت کا ایک نیا لفظ، آسان اردو میں۔ آواز: اے آئی\n\n"
                                  "#shorts #اے_آئی #آج_کا_اے_آئی_لفظ #فاروقی_اے_آئی_نیوز")[:4900],
          "tags": list(dict.fromkeys((d.get("tags") or []) + [d["term"], d.get("en", ""), "آج کا اے آئی لفظ", "AI Urdu", "shorts"]))}
    key = B._today() + "-w"
    try:
        from . import seo as SEO
        SEO.attach("word", key, d, sd, [d["term"], d["meaning"], d["example"], d["script"]])
    except Exception as e:
        print("SEO پیکیج نہیں بنا:", e)
    d["stories"] = [{"headline": f"آج کا اے آئی لفظ: {d['term']}"}]
    vmid, mids = B.deliver(final, B.ROOT / "word_thumb.jpg", sd, d, key=key, label=f"📘 آج کا اے آئی لفظ — «{d['term']}»",
                           size=(1080, 1920), when=when)
    ytinfo = B._yt_upload(final, None, sd, playlist=PLAYLIST, when=when)
    st = read_json(B.STATE) if B.STATE.exists() else {}
    st.setdefault("days", {})[key] = {"status": "pending", "vmid": vmid, "mids": mids, "kind": "word", **ytinfo}
    st.pop("redo_w", None)
    st["days"] = dict(sorted(st["days"].items())[-60:])
    write_json(B.STATE, st)
    used = read_json(USED) if USED.exists() else []
    used.append({"n": d["n"], "term": d["term"], "en": d.get("en", ""), "date": B._today()})
    write_json(USED, used)
    return True


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "sample":
        make(sample=True)
