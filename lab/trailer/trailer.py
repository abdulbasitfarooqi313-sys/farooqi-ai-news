"""فاروقی اے آئی نیوز — چینل ٹریلر (16:9، تقریباً ایک منٹ)۔ آواز: مائیکروسافٹ کی مفت اردو آواز (جیمنائی کا کوٹا بچانے کے لیے)۔
python lab/trailer/trailer.py → trailer.mp4"""
import asyncio, json, os, subprocess, sys, tempfile
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from news import bulletin as B
from news.explainer import _chunks

HERE = Path(__file__).parent
LINES = [
    ("s2", "مصنوعی ذہانت ہر روز دنیا بدل رہی ہے۔ نئی ایجادات، نئے ٹولز، اور نئے مواقع۔"),
    ("s3", "مگر یہ ساری خبریں زیادہ تر انگریزی میں ہوتی ہیں۔ فاروقی اے آئی نیوز آپ کے لیے لاتا ہے یہی دنیا، آسان اردو میں۔"),
    ("s4", "ہفتہ، پیر اور بدھ کو، تفصیلی نیوز بلیٹن، مستند ذرائع کے حوالے سے۔"),
    ("s5", "اتوار، منگل اور جمعرات کو، اے آئی فلیش۔ دنیا بھر سے پندرہ سے زیادہ سرخیاں، صرف دو منٹ میں۔"),
    ("s6", "اور جلد ہی، ہر جمعہ کو، اے آئی بیٹھک، جہاں سارہ اور احمد اے آئی کے کسی ایک موضوع پر کھل کر بات کریں گے۔"),
    ("s7", "کوئی سنسنی نہیں، صرف حقائق۔ طلبہ، نوجوانوں، اور ہر اس شخص کے لیے جو آنے والے کل کو سمجھنا چاہتا ہے۔"),
    ("s8", "ہر روز شام پانچ بجے سعودی وقت، اور پاکستان میں سات بجے۔ ابھی سبسکرائب کیجیے اور بیل آئیکن دبائیے۔ فاروقی اے آئی نیوز، نئے آفاق کی دریافت۔"),
]
PHOTOS = ["robot hand technology", "futuristic city technology", "reading news smartphone", "industrial robot arm",
          "technology conference stage", "smartphone night city", "circuit board"]


def pix(q: str, dest: Path) -> str:
    pk = os.environ.get("PEXELS_API_KEY", "").strip()
    if pk:
        try:
            r = requests.get("https://api.pexels.com/v1/search", headers={"Authorization": pk}, timeout=30,
                             params={"query": q, "orientation": "landscape", "per_page": 5, "size": "large"})
            ph = r.json()["photos"][0]
            dest.write_bytes(requests.get(ph["src"]["large2x"], timeout=60).content)
            return B._b64(dest, "image/jpeg")
        except Exception as e:
            print("pexels fail", q, e)
    key = os.environ.get("PIXABAY_API_KEY", "").strip()
    try:
        r = requests.get("https://pixabay.com/api/", timeout=30, params={"key": key, "q": q, "image_type": "photo",
                         "orientation": "horizontal", "safesearch": "true", "per_page": 10, "min_width": 1920})
        bad = ("woman", "man", "girl", "boy", "person", "people", "child", "face", "female", "male", "lady", "photographer", "portrait", "human")
        hits = [x for x in r.json()["hits"] if not any(b in (x.get("tags") or "").lower() for b in bad)]
        h = hits[0]
        dest.write_bytes(requests.get(h["largeImageURL"], timeout=60).content)
        return B._b64(dest, "image/jpeg")
    except Exception as e:
        print("photo fail", q, e)
        return ""


VOICES = {"F": "Aoede", "M": "Orus"}      # جیمنائی: خاتون / مرد


def gem(text: str, voice: str, dest: Path) -> Path:
    import base64, re, time, wave
    for attempt in range(5):
        r = requests.post("https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent",
                          params={"key": os.environ.get("GEMINI_BACKUP_KEY") or os.environ["GEMINI_API_KEY"]}, timeout=240, json={
                              "contents": [{"parts": [{"text": "Read the following Urdu text aloud:\n\n" + text}]}],
                              "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {
                                  "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}}})
        c = (r.json().get("candidates") or [{}])[0] if r.ok else {}
        if c.get("content"):
            part = c["content"]["parts"][0]["inlineData"]
            rate = int(re.search(r"rate=(\d+)", part.get("mimeType", "rate=24000")).group(1))
            raw = dest.with_suffix(".raw.wav")
            with wave.open(str(raw), "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(base64.b64decode(part["data"]))
            return B._norm(raw, dest, pad=0.1)
        print("TTS try", attempt, r.status_code, c.get("finishReason"), r.text[:160].replace("\n", " "))
        if r.status_code == 429:
            if re.search(r"PerDay|per_day|limit: 0", r.text, flags=re.I):
                break
            m = re.search(r'"retryDelay":\s*"(\d+)', r.text)
            time.sleep(min(65, int(m.group(1)) + 3 if m else 30))
            continue
        time.sleep(6)
    raise RuntimeError("Gemini TTS failed")


def main():
    import edge_tts
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        parts, t = [], 0.0
        sc, caps = [], []

        def add(p):
            nonlocal t
            parts.append(p)
            t0, t = t, t + B._dur(p)
            return t0, t
        tune = tmp / "tune.wav"
        B._ff("-i", str(B.A / "headlines_logo.mp3"), "-t", "4.2", "-af", "volume=0.9,afade=t=out:st=3.2:d=1", "-ar", "44100", "-ac", "2",
              "-c:a", "pcm_s16le", str(tune))
        a, b = add(tune)
        sc.append({"id": "s1", "t0": 0.0, "t1": b})
        for i, (sid, text) in enumerate(LINES):
            who = "F" if i % 2 == 0 else "M"
            if os.environ.get("TRAILER_TTS") == "gemini":
                if i:
                    import time
                    time.sleep(22)                      # مفت حد: فی منٹ 3 درخواستیں
                w = gem(text, VOICES[who], tmp / f"l{i}.wav")
            else:
                mp3 = tmp / f"l{i}.mp3"
                asyncio.run(edge_tts.Communicate(text, "ur-PK-UzmaNeural" if who == "F" else "ur-PK-AsadNeural", rate="-2%").save(str(mp3)))
                w = B._norm(mp3, tmp / f"l{i}.wav", pad=0.1)
            s0, _ = add(B._sil(0.35, tmp / f"g{i}.wav"))
            v0, v1 = add(w)
            tail = 2.6 if sid == "s8" else 0.45
            _, e1 = add(B._sil(tail, tmp / f"h{i}.wav"))
            sc.append({"id": sid, "t0": round(s0, 2), "t1": round(e1, 2)})
            caps += _chunks(text, v0, v1, max_words=8)
        lst = tmp / "l.txt"
        lst.write_text("".join(f"file '{p}'\n" for p in parts))
        voice = tmp / "voice.wav"
        B._ff("-f", "concat", "-safe", "0", "-i", str(lst), "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(voice))
        dur = B._dur(voice)
        audio = tmp / "audio.wav"
        B._ff("-i", str(voice), "-stream_loop", "-1", "-i", str(B.A / "bed.m4a"), "-filter_complex",
              f"[1]volume=0.13,afade=t=in:st=3.5:d=1.5,afade=t=out:st={dur - 2.5:.2f}:d=2.5[b];"
              "[0][b]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-15:TP=-1.5[a]",
              "-map", "[a]", "-t", f"{dur:.2f}", "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(audio))
        html = (HERE / "trailer.html").read_text(encoding="utf-8")
        rep = {"__NQFONT__": B.FONT.as_uri(), "__LOGO__": B._b64(B.A / "logo_round.png", "image/png"),
               "__NFDATA__": json.dumps({"sc": sc, "caps": caps}, ensure_ascii=False)}
        for i, q in enumerate(PHOTOS):
            rep[f"__P{i}__"] = pix(q, tmp / f"p{i}.jpg")
        for k, v in rep.items():
            html = html.replace(k, v)
        page = tmp / "t.html"
        page.write_text(html, encoding="utf-8")
        silent = tmp / "silent.mp4"
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            br = B._launch(pw)
            pg = br.new_page(viewport={"width": 1920, "height": 1080})
            pg.goto(page.as_uri())
            pg.wait_for_function("document.title==='ready'", timeout=90000)
            ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", "25", "-c:v", "mjpeg", "-i", "-",
                                   "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p", str(silent)], stdin=subprocess.PIPE)
            for f in range(int(dur * 25)):
                pg.evaluate(f"render({f / 25})")
                ff.stdin.write(pg.screenshot(type="jpeg", quality=94))
            ff.stdin.close(); ff.wait(); br.close()
        s5 = next(s for s in sc if s["id"] == "s5")
        a0, a1 = s5["t0"] + 0.35, s5["t1"] - 0.35
        out = ROOT / "trailer.mp4"
        B._ff("-i", str(silent), "-i", str(HERE / "flash_clip.mp4"), "-i", str(audio), "-filter_complex",
              f"[1]scale=372:661,setpts=PTS+{a0:.2f}/TB[ph];[0][ph]overlay=264:113:enable='between(t,{a0:.2f},{a1:.2f})':eof_action=pass[v]",
              "-map", "[v]", "-map", "2:a", "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
              "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out))
        print(f"TRAILER ✅ {dur:.1f}s")


if __name__ == "__main__":
    main()
# rerun 02:40:31: edge male+female, robot photos
