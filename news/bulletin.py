"""فاروقی اے آئی نیوز — روزانہ ایک بلیٹن (ساڑھے تین سے چار منٹ)۔

ترتیب: انٹرو (مقررہ) → نیوز روم: میزبان کا آغاز → ہر خبر: سنہری پٹی «خبر ۱» + میزبان کی سرخی
(پوری اسکرین) → ورچوئل نامہ نگار کی تفصیل (دو خانے: بائیں موضوع کا متحرک منظر + نامہ نگار) → آؤٹرو (مقررہ)۔
خبریں: معتبر انگریزی RSS (پچھلے 48 گھنٹے) → Gemini اردو اسکرپٹ صرف انہی خبروں سے (نئی بات نہیں گھڑتا)۔
آواز: میزبان Kore (زنانہ)، نامہ نگار Charon (مردانہ) — صرف متن، کوئی ہدایت نہیں پڑھوائی جاتی۔
نتیجہ: ٹیلیگرام پر ویڈیو (✅/❌) + تھمب نیل + SEO اور سوشل میڈیا کا پورا پیکیج۔

python -m news.bulletin          → آج کا بلیٹن (اگر ابھی نہیں بنا)
python -m news.bulletin force    → دوبارہ بنائیں
"""
from __future__ import annotations

import base64
import datetime as dt
import email.utils
import html as _h
import json
import os
import re
import subprocess
import sys
import tempfile
import wave
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

from .base import (ROOT, read_json, write_json, generate_json, _norm, _split, SplitError, TTSQuota, _launch as _launch0,
                   tg_call, record_start, record_stop, send_text, send_video, send_photo, gemini_key)

A = ROOT / "studio"
STATE = ROOT / "state" / "news.json"
FONT = ROOT / "fonts" / "jameel-noori.ttf"
TZ = dt.timezone(dt.timedelta(hours=3))
FPS = 25
ANCHOR_VOICE, REPORTER_VOICE = "Kore", "Charon"
LOG: list[str] = []      # خرابی کی فائل میں جانے والے نوٹ
TOPICS = ["ai", "robot", "chip", "phone", "health", "car", "space", "finance", "security", "education", "law", "data", "media"]
URDU_MONTHS = ["جنوری", "فروری", "مارچ", "اپریل", "مئی", "جون", "جولائی", "اگست", "ستمبر", "اکتوبر", "نومبر", "دسمبر"]
UD = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
ORD = ["پہلی خبر", "دوسری خبر", "تیسری خبر", "چوتھی خبر", "پانچویں خبر", "چھٹی خبر"]

FEEDS = [
    "https://news.google.com/rss/search?q=%22artificial+intelligence%22+OR+OpenAI+OR+Gemini+OR+Anthropic+when:2d&hl=en-US&gl=US&ceid=US:en",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "https://venturebeat.com/category/ai/feed/",
    "https://www.artificialintelligence-news.com/feed/",
    "https://news.mit.edu/rss/topic/artificial-intelligence2",
]


def _today() -> str:
    return dt.datetime.now(TZ).strftime("%Y-%m-%d")


def urdu_date(d: dt.date | None = None, latin: bool = False) -> str:
    """latin=True: ویڈیو/تصویر کے لیے انگریزی ہندسے (نستعلیق فونٹ میں اردو ہندسے الجھ جاتے ہیں)"""
    d = d or dt.datetime.now(TZ).date()
    f = (lambda x: str(x)) if latin else (lambda x: str(x).translate(UD))
    return f"{f(d.day)} {URDU_MONTHS[d.month - 1]} {f(d.year)}"


def _ff(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True, timeout=1800)


def _dur(p: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


# ---------------- خبریں ----------------

def _txt(s: str | None) -> str:
    s = re.sub(r"<[^>]+>", " ", _h.unescape(s or ""))
    return re.sub(r"\s+", " ", s).strip()


def fetch(max_age_h: int = 48) -> list[dict]:
    now = dt.datetime.now(dt.timezone.utc)
    out, seen = [], set()
    for url in FEEDS:
        try:
            r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0 (FarooqiAINews RSS reader)"})
            root = ET.fromstring(r.content)
        except Exception as e:
            print(f"فیڈ نہ ملی: {url[:60]} — {e}")
            continue
        ns = {"a": "http://www.w3.org/2005/Atom"}
        items = root.findall(".//item") or root.findall(".//a:entry", ns)
        for it in items[:25]:
            g = lambda tag: (it.findtext(tag) or it.findtext(f"a:{tag}", namespaces=ns) or "")
            title = _txt(g("title"))
            link = g("link") or ((it.find("a:link", ns).get("href")) if it.find("a:link", ns) is not None else "")
            desc = _txt(g("description") or g("summary") or g("content"))[:700]
            when = g("pubDate") or g("published") or g("updated")
            try:
                t = email.utils.parsedate_to_datetime(when) if "," in when else dt.datetime.fromisoformat(when.replace("Z", "+00:00"))
                if t.tzinfo is None:
                    t = t.replace(tzinfo=dt.timezone.utc)
                if (now - t).total_seconds() > max_age_h * 3600:
                    continue
            except Exception:
                t = None
            src = (it.findtext("source") or re.sub(r"^https?://(www\.)?([^/]+).*", r"\2", url))
            key = re.sub(r"\W+", "", title.lower())[:60]
            if not title or key in seen:
                continue
            seen.add(key)
            out.append({"title": title, "summary": desc, "source": _txt(src), "link": link.strip(),
                        "when": t.isoformat() if t else ""})
    print(f"{len(out)} خبریں ملیں")
    return out


SCRIPT_SYSTEM = """آپ «فاروقی اے آئی نیوز» کے سینئر اردو نیوز ایڈیٹر اور اسکرپٹ رائٹر ہیں — مصنوعی ذہانت (AI) کی خبروں کا روزانہ اردو بلیٹن۔
ناظرین عام پاکستانی/ہندوستانی اردو دان ہیں: زبان سادہ، شستہ، ٹی وی خبروں والی؛ انگریزی اصطلاح ہو تو اردو رسم الخط میں لکھیں اور پہلی بار مختصر وضاحت کریں (مثلاً «چیٹ بوٹ یعنی بات کرنے والا کمپیوٹر پروگرام»)۔
سختی سے: صرف دی گئی خبروں کے حقائق؛ کوئی عدد، نام، تاریخ یا دعویٰ اپنی طرف سے نہ گھڑیں؛ غیر یقینی بات کو «بتایا جا رہا ہے»/«کمپنی کے مطابق» سے بیان کریں۔ ہر خبر میں ماخذ کا نام آئے (مثلاً «ٹیک کرنچ کے مطابق»)۔
سنسنی، مبالغہ، سیاسی رائے اور غیر اخلاقی/نامناسب موضوع سے پرہیز۔ کسی شخص کا مذاق نہیں۔
بلیٹن پہلے ہی ایک انٹرو اور آؤٹرو رکھتا ہے (آؤٹرو میں «اللہ حافظ» اور سبسکرائب کی بات ہے) — اس لیے آپ کے اسکرپٹ میں الوداع یا سبسکرائب کی بات نہ ہو۔
بولا جانے والا ہر متن صرف وہی ہو جو پڑھا جائے گا — کوئی بریکٹ، ہدایت، ایموجی، ہیش ٹیگ یا انگریزی حروف نہیں (اعداد اردو الفاظ یا ہندسوں میں ٹھیک)۔
صرف JSON:
{"opening": "میزبان کا آغاز، 30 تا 40 الفاظ: «السلام علیکم! فاروقی اے آئی نیوز میں خوش آمدید۔ میں ہوں آپ کی میزبان…» پھر آج کی خبروں کی جھلک",
 "stories": [ ٹھیک 5 خبریں، سب سے اہم پہلے، مختلف موضوعات:
   {"headline": "سرخی، 4 تا 8 الفاظ، اردو",
    "topic": "ان میں سے ایک: ai, robot, chip, phone, health, car, space, finance, security, education, law, data, media",
    "location": "خبر کا مقام اردو میں «شہر، ملک» (معلوم نہ ہو تو کمپنی کا صدر مقام؛ وہ بھی نہ ہو تو «عالمی»)",
    "anchor": "میزبان کی سرخی والی بات، 22 تا 30 الفاظ، آخر میں نامہ نگار کی طرف رخ، مثلاً «…تفصیل بتا رہے ہیں ہمارے ورچوئل نامہ نگار۔»",
    "reporter": "نامہ نگار کی تفصیل، 45 تا 60 الفاظ: کیا ہوا، کس نے کیا، عام آدمی کے لیے اس کا مطلب کیا ہے؛ ماخذ کا نام",
    "source": "ماخذ کا نام (انگریزی)", "link": "دیا گیا لنک"} ],
 "ticker": ["5 تا 6 مختصر شہ سرخیاں، ہر ایک 4 تا 8 الفاظ"],
 "thumb_text": "تھمب نیل کے لیے 3 تا 5 الفاظ، سب سے بڑی خبر",
 "youtube_title": "یوٹیوب عنوان (زیادہ سے زیادہ 90 حروف): سب سے بڑی خبر + | فاروقی اے آئی نیوز",
 "summary": "یوٹیوب تفصیل کا پہلا پیراگراف، 2 تا 3 جملے",
 "tags": ["15 تا 20 ٹیگ اردو اور انگریزی ملا کر"],
 "social": {"facebook": "3 تا 5 سطریں + 4 ہیش ٹیگ", "instagram": "کیپشن 3 تا 5 سطریں + خالی سطر + 12 تا 15 ہیش ٹیگ",
            "tiktok": "1 تا 2 سطریں + 5 تا 7 ہیش ٹیگ", "x": "زیادہ سے زیادہ 230 حروف + 2 ہیش ٹیگ",
            "whatsapp": "2 تا 3 سطریں", "pinned": "یوٹیوب پن کمنٹ: آج کی کسی خبر پر ناظرین سے ایک سوال"}}"""


def script(items: list[dict], feedback: str | None = None) -> dict:
    listing = "\n\n".join(f"[{i + 1}] {it['title']}\nماخذ: {it['source']} · {it['when'][:10]}\nخلاصہ: {it['summary']}\nلنک: {it['link']}"
                          for i, it in enumerate(items[:40]))
    user = f"آج کی تاریخ: {urdu_date()}\n\nپچھلے دو دن کی AI خبریں:\n\n{listing}"
    if feedback:
        user += f"\n\nمالک کی ہدایت (اس کا خاص خیال رکھیں): {feedback}"
    d = generate_json(SCRIPT_SYSTEM, user)
    st = [s for s in d.get("stories", []) if s.get("anchor") and s.get("reporter")][:5]
    if len(st) < 3:
        raise RuntimeError("اسکرپٹ میں کافی خبریں نہیں")
    for s in st:
        if s.get("topic") not in TOPICS:
            s["topic"] = "ai"
        s["location"] = s.get("location") or "عالمی"
    d["stories"] = st
    return d


# ---------------- آواز ----------------

def _speak(texts: list[str], voice: str, tmp: Path, tag: str) -> list[Path]:
    """سب ٹکڑے ایک Gemini کال میں (کوٹہ بچانے کے لیے) — صرف متن؛ پھر وقفوں/Gemini اوقات سے کاٹ کر الگ۔
    کاٹنا ممکن نہ ہو تو ہر ٹکڑا الگ کال میں۔"""
    models = ["gemini-2.5-flash-preview-tts"]

    def call(text: str, model: str):
        """ایک Gemini TTS کال — ناکامی کی اصل وجہ لاگ میں (اگلی درستی کے لیے)"""
        import base64 as b64, time
        prompt = "Read the following Urdu text aloud:\n\n" + text      # صرف پڑھنے کا اشارہ — یہ جملہ بولا نہیں جاتا
        for attempt in range(3):
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                              params={"key": gemini_key()}, timeout=240, json={
                                  "contents": [{"parts": [{"text": prompt}]}],
                                  "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {
                                      "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}}})
            if r.status_code == 429:
                if re.search(r"PerDay|per_day|per day|RequestsPerDay|limit: 0", r.text, flags=re.I):
                    LOG.append(f"TTS {voice} 429: {r.text[:400]}")
                    raise TTSQuota("آواز (Gemini TTS) کا آج کا مفت کوٹہ ختم ہو گیا")
                m = re.search(r'"retryDelay":\s*"(\d+)', r.text)
                time.sleep(min(60, int(m.group(1)) + 2 if m else 30))
                continue
            if r.status_code in (500, 503):
                time.sleep(15)
                continue
            break
        if not r.ok:
            LOG.append(f"TTS {voice} {r.status_code}: {r.text[:300]}"); print(LOG[-1])
            return None
        try:
            part = r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]
        except Exception:
            LOG.append(f"TTS {voice} بغیر آواز: {r.text[:300]}"); print(LOG[-1])
            return None
        m = re.search(r"rate=(\d+)", part.get("mimeType", ""))
        return b64.b64decode(part["data"]), int(m.group(1)) if m else 24000

    def one(text: str, dest: Path) -> Path | None:
        import time
        for k in range(1):                    # ناکامی پر وہی متن دوبارہ نہیں — کوٹہ بچانے کے لیے سیدھا آدھا آدھا
            got = None
            for m in models:
                got = call(text, m)
                if got:
                    break
            if got:
                pcm, rate = got
                raw = dest.with_suffix(".raw.wav")
                with wave.open(str(raw), "wb") as w:
                    w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(pcm)
                return _norm(raw, dest, pad=0.15)
        return None

    def must(text: str, dest: Path) -> Path:
        p = one(text, dest)
        if not p:
            raise RuntimeError("آواز (Gemini TTS) نہیں بن سکی")
        return p

    def group(ts: list[str], tg_: str) -> list[Path]:
        """ٹکڑوں کا گروپ ایک کال میں؛ نہ بنے تو آدھا آدھا کر کے"""
        if len(ts) == 1:
            return [must(ts[0], tmp / f"{tg_}_one.wav")]
        if len(ts) > 3:                        # لمبے متن پر Gemini اکثر خالی (finishReason OTHER) لوٹاتا ہے
            h = (len(ts) + 1) // 2
            return group(ts[:h], tg_ + "a") + group(ts[h:], tg_ + "b")
        whole = one("\n\n".join(t.strip() for t in ts), tmp / f"{tg_}_all.wav")
        if whole:
            try:
                return _split(whole, ts, tmp, tg_)
            except SplitError as e:
                print(f"   {e} — آدھا آدھا")
        h = len(ts) // 2
        return group(ts[:h], tg_ + "a") + group(ts[h:], tg_ + "b")

    return group(texts, tag)


def _trim(src: Path, dst: Path) -> Path:
    """ٹکڑے کے شروع/آخر کی لمبی خاموشی کاٹ کر 0.15s رکھیں"""
    _ff("-i", str(src), "-af", "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.1,"
        "areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.15,areverse",
        "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(dst))
    return dst


def _sil(sec: float, dst: Path) -> Path:
    _ff("-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", f"{sec:.3f}", "-c:a", "pcm_s16le", str(dst))
    return dst


def _energy(wav: Path, n_frames: int, mask: list[tuple[float, float]]) -> list[float]:
    """میزبان کی آواز کی توانائی (ہر فریم) — سر کی ہلکی جنبش اسی کے ساتھ؛ صرف میزبان کے حصوں میں"""
    import numpy as np
    with wave.open(str(wav)) as w:
        sr, ch = w.getframerate(), w.getnchannels()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)
    if ch == 2:
        x = x.reshape(-1, 2).mean(1)
    hop = sr // FPS
    e = np.array([np.sqrt(np.mean(x[i * hop:(i + 1) * hop] ** 2)) if i * hop < len(x) else 0 for i in range(n_frames)])
    e = e / (np.percentile(e[e > 0], 95) if (e > 0).any() else 1)
    on = np.zeros(n_frames)
    for a, b in mask:
        on[int(a * FPS):int(b * FPS)] = 1
    e = np.clip(e, 0, 1) * on
    k = np.ones(5) / 5
    e = np.convolve(e, k, "same")
    return [round(float(v), 3) for v in e]


EDGE_VOICES = {ANCHOR_VOICE: "ur-PK-UzmaNeural", REPORTER_VOICE: "ur-PK-AsadNeural"}


def _edge(texts: list[str], voice: str, tmp: Path, tag: str) -> list[Path]:
    """Microsoft Edge کی مفت اردو آواز (کوئی کوٹہ نہیں) — Gemini کی آواز نہ ملے تو"""
    import asyncio
    import edge_tts
    out = []
    for i, t in enumerate(texts):
        mp3 = tmp / f"{tag}e{i}.mp3"
        for k in range(3):
            try:
                asyncio.run(edge_tts.Communicate(t.strip(), EDGE_VOICES[voice], rate="-4%").save(str(mp3)))
                break
            except Exception as e:
                LOG.append(f"edge-tts: {str(e)[:200]}")
                import time
                time.sleep(5 * (k + 1))
        else:
            raise RuntimeError("Edge کی آواز بھی نہیں بن سکی")
        out.append(_norm(mp3, tmp / f"{tag}e{i}.wav", pad=0.15))
    return out


def _voices(d: dict, tmp: Path) -> tuple[list[Path], list[Path]]:
    sts = d["stories"]
    at = [d["opening"]] + [s["anchor"] for s in sts]
    rt = [s["reporter"] for s in sts]
    if os.environ.get("NEWS_TTS", "gemini") == "gemini":
        try:
            return _speak(at, ANCHOR_VOICE, tmp, "anc"), _speak(rt, REPORTER_VOICE, tmp, "rep")
        except Exception as e:                      # کوٹہ یا خالی جواب — پورا بلیٹن ایک ہی قسم کی آواز میں
            LOG.append(f"Gemini آواز نہ ملی ({str(e)[:120]}) — Edge کی آواز")
            print(LOG[-1])
    return _edge(at, ANCHOR_VOICE, tmp, "anc"), _edge(rt, REPORTER_VOICE, tmp, "rep")


def build_audio(d: dict, tmp: Path) -> tuple[Path, dict]:
    """بلیٹن کا درمیانی حصہ: آواز کی ترتیب + ہر حصے کے اوقات"""
    sts = d["stories"]
    anc, rep = _voices(d, tmp)
    anc = [_trim(p, tmp / f"ancT{i}.wav") for i, p in enumerate(anc)]
    rep = [_trim(p, tmp / f"repT{i}.wav") for i, p in enumerate(rep)]
    sting = tmp / "sting.wav"
    _ff("-i", str(A / "sting.wav"), "-af", "apad=pad_dur=0.1", "-t", "1.6", "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(sting))
    parts, t = [], 0.0
    tl = {"split": [[0, 0]], "stories": [], "wipes": [], "anchor": []}

    def add(p: Path, kind: str):
        nonlocal t
        du = _dur(p)
        parts.append(p)
        if kind == "anchor":
            tl["anchor"].append((t, t + du))
        t0 = t
        t += du
        return t0, t

    add(_sil(0.6, tmp / "s0.wav"), "gap")
    add(anc[0], "anchor")
    for i, s in enumerate(sts):
        add(_sil(0.35, tmp / f"g{i}a.wav"), "gap")
        w0, _ = add(sting, "sting")
        tl["wipes"].append([round(w0, 2), ORD[i]])
        a0, a1 = add(anc[i + 1], "anchor")
        add(_sil(0.55, tmp / f"g{i}b.wav"), "gap")
        r0, r1 = add(rep[i], "reporter")
        # میزبان پوری اسکرین → نامہ نگار سے بات پر «زوم اِن» دو خانے → واپس
        tl["split"] += [[round(max(a1 - 0.4, a0), 2), 0], [round(r0 + 0.5, 2), 1], [round(r1 + 0.1, 2), 1], [round(r1 + 1.0, 2), 0]]
        tl["stories"].append({"t0": round(w0, 2), "t1": round(r1 + 0.3, 2), "n": ORD[i], "h": s["headline"], "topic": s["topic"], "loc": s["location"]})
    add(_sil(1.2, tmp / "s9.wav"), "gap")
    lst = tmp / "body.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    voice = tmp / "body_voice.wav"
    _ff("-f", "concat", "-safe", "0", "-i", str(lst), "-c:a", "pcm_s16le", str(voice))
    tl["dur"] = round(_dur(voice), 2)
    tl["energy"] = _energy(voice, int(tl["dur"] * FPS) + 2, tl["anchor"])
    mixed = tmp / "body_audio.wav"
    _ff("-i", str(voice), "-stream_loop", "-1", "-i", str(A / "bed.m4a"), "-filter_complex",
        f"[1]volume=0.07,afade=t=in:d=1.5,afade=t=out:st={tl['dur'] - 1.5:.2f}:d=1.5[b];"
        f"[0][b]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-16:TP=-1.5[a]",
        "-map", "[a]", "-t", f"{tl['dur']:.2f}", "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(mixed))
    return mixed, tl


# ---------------- تصویر ----------------

def _b64(p: Path, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()


def page(d: dict, tl: dict) -> str:
    html = (A / "newsroom.html").read_text(encoding="utf-8")
    tick = " <b>◆</b> ".join(_h.escape(x) for x in (d.get("ticker") or [s["headline"] for s in d["stories"]]))
    data = {k: tl[k] for k in ("split", "stories", "wipes", "dur", "energy")}
    rep = {"__LOGO__": _b64(A / "logo_round.png", "image/png"), "__NQFONT__": FONT.as_uri(),
           "__ABG__": _b64(A / "anchor_bg.jpg", "image/jpeg"), "__AFG__": _b64(A / "anchor_fg.png", "image/png"),
           "__ABLINK__": _b64(A / "anchor_blink.png", "image/png"), "__IMGB__": _b64(A / "reporter.jpg", "image/jpeg"),
           "__SCENESJS__": (A / "scenes.js").read_text(encoding="utf-8"), "__TICKER__": (tick + " <b>◆</b> ") * 3,
           "__DATE__": urdu_date(latin=True), "__NFDATA__": json.dumps(data, ensure_ascii=False)}
    return re.sub(r"__[A-Z]+__", lambda m: rep.get(m.group(0), m.group(0)), html)


def _launch(pw):
    return _launch0(pw)


def render_body(d: dict, tl: dict, audio: Path, out: Path, tmp: Path) -> Path:
    from playwright.sync_api import sync_playwright
    p = tmp / "newsroom_built.html"
    p.write_text(page(d, tl), encoding="utf-8")
    silent = tmp / "body_silent.mp4"
    with sync_playwright() as pw:
        br = _launch(pw)
        pg = br.new_page(viewport={"width": 1920, "height": 1080})
        pg.goto(p.as_uri())
        pg.wait_for_function("document.title==='ready'", timeout=90000)
        ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg",
                               "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(silent)],
                              stdin=subprocess.PIPE)
        n = int(tl["dur"] * FPS)
        for f in range(n):
            pg.evaluate(f"render({f / FPS})")
            ff.stdin.write(pg.screenshot(type="jpeg", quality=88))
            if f % (FPS * 30) == 0:
                print(f"   فریم {f}/{n}")
        ff.stdin.close()
        ff.wait()
        br.close()
    _ff("-i", str(silent), "-i", str(audio), "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(out))
    return out


def assemble(body: Path, out: Path) -> Path:
    """انٹرو + نیوز روم + آؤٹرو — ایک ہی شکل (1920×1080، 30fps، سٹیریو) میں جوڑ کر"""
    v = "fps=30,scale=1920:1080,setsar=1,format=yuv420p"
    a = "aresample=44100,aformat=channel_layouts=stereo"
    _ff("-i", str(A / "intro.mp4"), "-i", str(body), "-i", str(A / "outro.mp4"), "-filter_complex",
        f"[0:v]{v}[v0];[0:a]{a}[a0];[1:v]{v}[v1];[1:a]{a}[a1];[2:v]{v}[v2];[2:a]{a}[a2];"
        "[v0][a0][v1][a1][v2][a2]concat=n=3:v=1:a=1[v][a]",
        "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", str(out))
    return out


THUMB = """<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{font-family:NQ;src:url('__NQFONT__')}*{margin:0;padding:0;box-sizing:border-box}
body{width:1280px;height:720px;overflow:hidden;background:#050b33}
#bg{position:absolute;inset:0;background:url('__ABG__') 45% 35%/130% auto no-repeat}
#fg{position:absolute;left:0;top:0}
#shade{position:absolute;inset:0;background:linear-gradient(90deg,rgba(5,11,51,.0) 0%,rgba(5,11,51,.25) 38%,rgba(5,11,51,.92) 60%,#050b33 100%)}
#sc{position:absolute;right:0;top:0;width:560px;height:720px;opacity:.55}
#logo{position:absolute;right:34px;top:28px;width:120px;height:120px;border-radius:50%;background:url('__LOGO__') center/cover;box-shadow:0 0 0 4px #e2b84f,0 0 30px rgba(95,180,255,.7)}
#badge{position:absolute;right:170px;top:52px;font-family:NQ;font-size:44px;color:#0a1550;background:linear-gradient(180deg,#ffe39a,#d4a53d);padding:0 26px 10px;border-radius:12px}
#t{position:absolute;right:34px;top:190px;width:640px;direction:rtl;text-align:right;font-family:NQ;font-size:96px;line-height:1.35;color:#fff;
 text-shadow:0 4px 0 #0a1550,0 0 30px rgba(0,0,0,.8)}
#t em{font-style:normal;color:#f0cf6a}
#d{position:absolute;right:34px;bottom:34px;font-family:NQ;font-size:38px;color:#cfe0ff;direction:rtl}
#live{position:absolute;left:28px;top:28px;font:700 30px Arial;color:#fff;background:#d42a2a;border-radius:8px;padding:6px 16px;letter-spacing:2px}
</style></head><body><div id="bg"></div><div id="sc"></div><div id="shade"></div>
<div id="logo"></div><div id="badge">اے آئی نیوز</div><div id="t">__TITLE__</div><div id="d">__DATE__</div><div id="live">● LIVE</div>
<script>__SCENESJS__</script><script>document.getElementById('sc').innerHTML=nfScene('__TOPIC__');nfAnimate(document.getElementById('sc'),2.2);
document.fonts.ready.then(()=>{document.title='ready'});</script></body></html>"""


def thumbnail(d: dict, out: Path, tmp: Path) -> Path:
    from playwright.sync_api import sync_playwright
    words = (d.get("thumb_text") or d["stories"][0]["headline"]).split()
    title = " ".join(words[:-1]) + (f" <em>{_h.escape(words[-1])}</em>" if words else "")
    rep = {"__NQFONT__": FONT.as_uri(), "__LOGO__": _b64(A / "logo_round.png", "image/png"),
           "__ABG__": _b64(A / "anchor.jpg", "image/jpeg"), "__SCENESJS__": (A / "scenes.js").read_text(encoding="utf-8"),
           "__TOPIC__": d["stories"][0]["topic"], "__TITLE__": title, "__DATE__": "فاروقی اے آئی نیوز · " + urdu_date(latin=True)}
    html = re.sub(r"__[A-Z]+__", lambda m: rep.get(m.group(0), m.group(0)), THUMB)
    p = tmp / "thumb.html"
    p.write_text(html, encoding="utf-8")
    with sync_playwright() as pw:
        br = _launch(pw)
        pg = br.new_page(viewport={"width": 1280, "height": 720})
        pg.goto(p.as_uri())
        pg.wait_for_function("document.title==='ready'", timeout=60000)
        pg.screenshot(path=str(out), type="jpeg", quality=92)
        br.close()
    return out


# ---------------- SEO اور ٹیلیگرام ----------------

def _ts(sec: float) -> str:
    return f"{int(sec // 60)}:{int(sec % 60):02d}"


def seo(d: dict, tl: dict, intro_dur: float) -> dict:
    ch = ["0:00 انٹرو", f"{_ts(intro_dur)} آج کی سرخیاں"]
    for s in tl["stories"]:
        ch.append(f"{_ts(intro_dur + s['t0'])} {s['h']}")
    ch.append(f"{_ts(intro_dur + tl['dur'])} اختتام")
    src = "\n".join(f"• {s.get('source', '')}: {s.get('link', '')}" for s in d["stories"] if s.get("link"))
    desc = (f"{d.get('summary', '')}\n\n📰 آج کی خبریں — {urdu_date()}\n" + "\n".join(f"{i + 1}. {s['headline']}" for i, s in enumerate(d["stories"]))
            + "\n\n⏱️ ابواب:\n" + "\n".join(ch) + (f"\n\n🔗 ماخذ:\n{src}" if src else "")
            + "\n\nفاروقی اے آئی نیوز — مصنوعی ذہانت کی دنیا، آسان اردو میں۔ نئے آفاق کی دریافت!\n"
            "سبسکرائب کریں، لائک کریں اور بیل آئیکن دبائیں۔\n\n"
            "#فاروقی_اے_آئی_نیوز #مصنوعی_ذہانت #اے_آئی #AINews #ArtificialIntelligence #UrduNews #TechNews")
    tags = list(dict.fromkeys((d.get("tags") or []) + ["فاروقی اے آئی نیوز", "Farooqi AI News", "AI News Urdu",
                                                        "مصنوعی ذہانت", "اے آئی خبریں", "Artificial Intelligence", "Tech News Urdu"]))
    title = d.get("youtube_title") or f"{d['stories'][0]['headline']} | فاروقی اے آئی نیوز"
    if "فاروقی" not in title:
        title = f"{title} | فاروقی اے آئی نیوز"
    return {"youtube_title": title[:100], "youtube_description": desc[:4900], "tags": tags}


def _tags_line(tags: list[str]) -> str:
    out, n = [], 0
    for t in tags:
        if n + len(t) + 2 > 480:
            break
        out.append(t)
        n += len(t) + 2
    return ", ".join(out)


def news_chat():
    """بلیٹن صرف «فاروقی اے آئی نیوز» کے اپنے ٹیلیگرام چینل/گروپ میں — نوائے فاروقی والی بوٹ چیٹ میں نہیں"""
    ns = read_json(STATE) if STATE.exists() else {}
    return ns.get("chat") or os.environ.get("TELEGRAM_CHAT_ID")


def deliver(video: Path, thumb: Path, sd: dict, d: dict) -> list:
    day = _today()
    so = d.get("social") or {}
    mins = _dur(video)
    chat = news_chat()

    def say(text: str, html: bool = True) -> int:
        kw = {"parse_mode": "HTML", "link_preview_options": {"is_disabled": True}} if html else {}
        return tg_call("sendMessage", chat_id=chat, text=text, **kw)["message_id"]

    record_start()
    say(f"📺 <b>فاروقی اے آئی نیوز — {urdu_date()}</b>\nآج کا بلیٹن ({int(mins // 60)}:{int(mins % 60):02d} منٹ)، "
                 f"تھمب نیل، اور یوٹیوب / سوشل میڈیا کا پورا پیکیج۔ ویڈیو پسند ہے تو ✅، دوبارہ بنوانی ہو تو ❌ "
                 f"(یا ویڈیو پر Reply کر کے لکھیں کیا بدلنا ہے)۔")
    vmid = send_video(chat, video, caption=f"📺 فاروقی اے آئی نیوز — {urdu_date()}\n" + "\n".join(f"{i + 1}. {s['headline']}" for i, s in enumerate(d["stories"])),
                      width=1920, height=1080,
                         buttons=[[{"text": "✅ منظور", "callback_data": f"nok:{day}"}, {"text": "❌ دوبارہ بنائیں", "callback_data": f"nno:{day}"}]])
    send_photo(chat, thumb, caption="🖼️ تھمب نیل (یوٹیوب Custom thumbnail)")
    blocks = [("▶️ یوٹیوب", "عنوان (Title)", sd["youtube_title"]), ("▶️ یوٹیوب", "تفصیل (Description)", sd["youtube_description"]),
              ("▶️ یوٹیوب", "ٹیگ (Tags)", _tags_line(sd["tags"])), ("▶️ یوٹیوب", "پلے لسٹ (Playlist)", "فاروقی اے آئی نیوز — روزانہ بلیٹن"),
              ("▶️ یوٹیوب", "پن کمنٹ", so.get("pinned", "")), ("📘 فیس بک", "پوسٹ", so.get("facebook", "")),
              ("📸 انسٹاگرام", "کیپشن", so.get("instagram", "")), ("🎵 ٹک ٹاک", "کیپشن", so.get("tiktok", "")),
              ("✖️ X", "پوسٹ", so.get("x", "")), ("💬 واٹس ایپ", "پیغام / اسٹیٹس", so.get("whatsapp", ""))]
    say("✅ <b>یوٹیوب اسٹوڈیو</b>: عنوان، تفصیل، ٹیگ نیچے سے پیسٹ کریں · Thumbnail اوپر والی تصویر · "
                 "Audience: Not made for kids · Language: Urdu · Category: <b>Science &amp; Technology</b> · "
                 "End screen: Subscribe + اگلی ویڈیو (آخری 20 سیکنڈ) · شائع ہونے کے بعد پن کمنٹ۔")
    for plat, field, text in blocks:
        if text:
            say(f"<b>{plat} — {field}</b>\n<pre>{_h.escape(text[:3800])}</pre>")
    mids = record_stop()
    return [vmid, mids]


# ---------------- چلانا ----------------

def make(feedback: str | None = None) -> None:
    if not news_chat():
        raise RuntimeError("ٹیلیگرام چیٹ معلوم نہیں — @farooqi_ai_news_bot کو /start بھیجیں")
    items = fetch()
    if len(items) < 3:
        raise RuntimeError("آج AI کی کافی خبریں نہیں ملیں")
    st = read_json(STATE) if STATE.exists() else {}
    used = set(st.get("used_titles", []))
    fresh = [i for i in items if re.sub(r"\W+", "", i["title"].lower())[:60] not in used] or items
    d = script(fresh, feedback)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        audio, tl = build_audio(d, tmp)
        print(f"درمیانی حصہ: {tl['dur']:.1f}s")
        body = render_body(d, tl, audio, tmp / "body.mp4", tmp)
        out = ROOT / "out_news.mp4"
        assemble(body, out)
        thumb = thumbnail(d, tmp / "thumb.jpg", tmp)
        sd = seo(d, tl, _dur(A / "intro.mp4"))
        vmid, mids = deliver(out, thumb, sd, d)
    day = _today()
    st = read_json(STATE) if STATE.exists() else {}
    st.setdefault("days", {})[day] = {"status": "pending", "vmid": vmid, "mids": mids,
                                      "headlines": [s["headline"] for s in d["stories"]]}
    st["used_titles"] = (st.get("used_titles", []) + [re.sub(r"\W+", "", i["title"].lower())[:60] for i in fresh[:40]])[-400:]
    st.pop("redo", None)
    st["days"] = dict(sorted(st["days"].items())[-30:])
    write_json(STATE, st)
    out.unlink(missing_ok=True)
    print("✅ بلیٹن بھیج دیا")


def tick(force: bool = False) -> None:
    st = read_json(STATE) if STATE.exists() else {}
    day = _today()
    redo = st.get("redo")
    if not force and not redo and day in st.get("days", {}):
        print("آج کا بلیٹن بن چکا")
        return
    make(feedback=(redo or {}).get("feedback") if isinstance(redo, dict) else None)


def poll() -> None:
    """اے آئی نیوز کے اپنے بوٹ کے بٹن (✅/❌) اور ویڈیو پر Reply والی ہدایت"""
    ns = read_json(STATE) if STATE.exists() else {}
    me = str(news_chat() or "")
    try:
        ups = tg_call("getUpdates", offset=ns.get("offset", 0), timeout=0, allowed_updates=["message", "callback_query"])
    except Exception as e:
        print(f"اے آئی نیوز بوٹ: {e}")
        return
    dispatch = False
    for up in ups:
        ns["offset"] = up["update_id"] + 1
        if cb := up.get("callback_query"):
            if str(cb["from"]["id"]) != me or ":" not in cb.get("data", ""):
                continue
            action, day = cb["data"].split(":", 1)
            chat, mid = cb["message"]["chat"]["id"], cb["message"]["message_id"]
            try:
                tg_call("editMessageReplyMarkup", chat_id=chat, message_id=mid, reply_markup={"inline_keyboard": []})
                tg_call("answerCallbackQuery", callback_query_id=cb["id"], text="ٹھیک ہے")
            except Exception:
                pass
            d = ns.setdefault("days", {}).setdefault(day, {})
            if action == "nok":
                d["status"] = "approved"
                tg_call("sendMessage", chat_id=chat, reply_parameters={"message_id": mid},
                         text="✅ آج کا بلیٹن منظور — اوپر کے پیکیج سے یوٹیوب پر لگا دیں۔")
            elif action == "nno":
                d["status"] = "redo"
                ns["redo"] = {"day": day, "feedback": None}
                dispatch = True
                tg_call("sendMessage", chat_id=chat, text="🔄 نیا بلیٹن بن رہا ہے (تقریباً 20–30 منٹ)۔ "
                         "کوئی خاص تبدیلی چاہیے تو اگلی بار ویڈیو پر Reply کر کے لکھیں۔")
        elif (msg := up.get("message")) and not me and msg.get("chat", {}).get("type") == "private" \
                and (msg.get("text") or "").startswith("/start"):
            me = str(msg["chat"]["id"])                 # پہلا /start = مالک کی چیٹ (TELEGRAM_CHAT_ID نہ ہو تو)
            ns["chat"] = msg["chat"]["id"]
            tg_call("sendMessage", chat_id=me, text="📺 فاروقی اے آئی نیوز — جڑ گیا ✅ روزانہ بلیٹن دوپہر تقریباً 2 بجے یہاں آئے گا۔")
        elif (msg := up.get("message")) and str(msg.get("chat", {}).get("id")) == me:
            rt, text = msg.get("reply_to_message"), (msg.get("text") or "").strip()
            day = next((k for k, v in ns.get("days", {}).items() if rt and v.get("vmid") == rt.get("message_id")), None)
            if day and text:
                ns["redo"] = {"day": day, "feedback": text}
                ns["days"][day]["status"] = "redo"
                dispatch = True
                tg_call("sendMessage", chat_id=me, text="🔄 ٹھیک ہے — آپ کی ہدایت کے ساتھ نیا بلیٹن بن رہا ہے (تقریباً 20–30 منٹ)۔")
            elif text.startswith("/start"):
                tg_call("sendMessage", chat_id=me, text="📺 فاروقی اے آئی نیوز — روزانہ بلیٹن دوپہر تقریباً 2 بجے یہاں آئے گا۔ "
                         "✅ منظور / ❌ دوبارہ، یا ویڈیو پر Reply کر کے ہدایت لکھیں۔")
    write_json(STATE, ns)
    if dispatch and os.environ.get("GITHUB_ACTIONS"):
        with open("/tmp/news_dispatch", "a") as f:
            f.write("bulletin.yml\n")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "poll":
        poll()
        sys.exit(0)
    try:
        tick(force=len(sys.argv) > 1 and sys.argv[1] == "force")
    except Exception as e:
        import traceback
        (ROOT / "state" / "news_error.txt").write_text(traceback.format_exc()[-3000:] + "\n\n" + "\n".join(LOG[-12:]), encoding="utf-8")
        try:
            send_text(news_chat(), f"⚠️ آج کا «فاروقی اے آئی نیوز» بلیٹن ابھی نہ بن سکا: {str(e)[:250]}\n"
                      "اگلے مقررہ وقت پر خود دوبارہ کوشش ہوگی۔", html=False)
        except Exception:
            pass
        raise
