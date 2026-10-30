"""🎙️ «اے آئی بیٹھک» — ہفتہ وار پوڈکاسٹ (جمعہ): سارہ اور احمد کی تقریباً 5 منٹ کی گفتگو، 16:9 ویڈیو۔

بدھ: اس ہفتے کی مستند خبروں سے 3 موضوع ٹیلیگرام پر — بٹن 1/2/3 سے چنیں، یا اس پیغام پر Reply کر کے اپنا موضوع لکھیں۔
جمعہ: چنا ہوا موضوع (کوئی نہ چنا ہو تو پہلا) → اسکرپٹ → جیمنائی آواز (ایک وقت میں ایک آواز — ٹریلر والا آزمودہ طریقہ،
پہلی چابی ختم ہو تو دوسری؛ پھر بھی ناکام ہو تو پوری گفتگو مائیکروسافٹ کی آوازوں میں) → ویڈیو → ٹیلیگرام ✅/❌ + یوٹیوب Private۔
✅ پر شام 5 بجے پبلک (بلیٹن والا طریقہ)۔ پلے لسٹ: «اے آئی بیٹھک — ہفتہ وار پوڈکاسٹ»۔

python -m news.podcast suggest   → موضوعات بھیجیں
python -m news.podcast           → آج جمعہ ہو اور نہ بنا ہو تو پوڈکاسٹ
python -m news.podcast force     → ابھی بنائیں
python -m news.podcast sample    → صرف ویڈیو podcast.mp4 (ٹیلیگرام/یوٹیوب نہیں)
"""
from __future__ import annotations

import asyncio
import base64
import datetime as dt
import html as _h
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

import requests

from . import bulletin as B
from . import flash as F
from .base import generate_json, read_json, write_json, send_text, tg_call, gemini_key, _norm
from .explainer import _chunks

SUGGEST_DAY, POD_DAY = 2, 4            # بدھ موضوع، جمعہ پوڈکاسٹ (مالک کی تقسیم: جمعہ = پوڈکاسٹ)
PLAYLIST = "اے آئی بیٹھک — ہفتہ وار پوڈکاسٹ"
VOICES = {"Sarah": "Aoede", "Ahmed": "Orus"}               # نمونے میں مالک کو پسند آئیں
EDGE = {"Sarah": "ur-PK-UzmaNeural", "Ahmed": "ur-PK-AsadNeural"}
NAME = {"Sarah": "سارہ", "Ahmed": "احمد"}
FPS = B.FPS
TTS_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent"

RULES = """سختی سے: صرف دی گئی خبروں کے حقائق — کوئی عدد، نام، تاریخ یا دعویٰ اپنی طرف سے نہیں؛ جو بات خبر میں نہیں وہ نہ کہیں۔
سرمایہ کاری کا کوئی مشورہ نہیں (کون سا شیئر/کرپٹو خریدیں یا بیچیں، کسی کمپنی کی قیمت بڑھے گی وغیرہ) — صرف خبر اور اس کا عام فہم مطلب۔
سیاسی رائے، سنسنی، افواہ اور کسی کمپنی کی تشہیر نہیں۔ انگریزی نام اردو رسم الخط میں (OpenAI = اوپن اے آئی، Google = گوگل)۔"""


def _week() -> str:
    """اس ہفتے کی پہچان: اس ہفتے کے بدھ کی تاریخ"""
    now = dt.datetime.now(B.TZ).date()
    return (now - dt.timedelta(days=(now.weekday() - SUGGEST_DAY) % 7)).isoformat()


def _news(days: int = 7) -> list[dict]:
    allitems = B.fetch(max_age_h=24 * days, feeds=F.FEEDS, per_feed=40)
    items = [it for it in allitems if F.trusted(it.get("source", ""))]
    print(f"مستند ذرائع: {len(items)} / {len(allitems)}")
    if len(items) < 15:
        raise RuntimeError(f"اس ہفتے کی کافی مستند خبریں نہیں ملیں ({len(items)})")
    return items


def _listing(items: list[dict], n: int = 150) -> str:
    return "\n".join(f"[{i + 1}] {it['title']} — {it['source']} · {it['summary'][:220]}" for i, it in enumerate(items[:n]))


# ---------------- بدھ: موضوعات ----------------

SUGGEST_SYS = f"""آپ اردو پوڈکاسٹ «اے آئی بیٹھک» (فاروقی اے آئی نیوز) کے پروڈیوسر ہیں۔ جمعہ کی قسط کے لیے اس ہفتے کی دی گئی خبروں سے
3 بالکل مختلف موضوع تجویز کریں جن پر 5 منٹ کی دلچسپ، معلوماتی گفتگو ہو سکے اور جو عام پاکستانی ناظر (طالب علم، نوجوان، پیشہ ور) کے لیے اہم ہوں۔
ہر موضوع کے پیچھے کم از کم 2 مستند خبریں ہوں۔ شیئر بازار/سرمایہ کاری والے موضوع سے پرہیز کریں۔
{RULES}
صرف JSON: {{"options": [{{"title": "موضوع، 4 تا 9 الفاظ", "why": "یہ کیوں اہم ہے، ایک جملہ", "n": [متعلقہ خبروں کے نمبر]}}]}}"""


def suggest(send: bool = True) -> None:
    items = _news(6)
    d = generate_json(SUGGEST_SYS, f"آج: {B.urdu_date()}\n\nاس ہفتے کی AI خبریں:\n{_listing(items)}")
    opts = []
    for o in d.get("options", [])[:3]:
        facts = []
        for n in o.get("n", [])[:8]:
            try:
                it = items[int(str(n).strip()) - 1]
                facts.append({k: it[k] for k in ("title", "source", "summary", "link")})
            except (ValueError, IndexError):
                pass
        if o.get("title") and facts:
            opts.append({"title": o["title"].strip(), "why": (o.get("why") or "").strip(), "facts": facts})
    if not opts:
        raise RuntimeError("موضوعات نہ بن سکے")
    week = _week()
    if not send:                                        # نمونہ: ٹیلیگرام پر کچھ نہیں
        st = read_json(B.STATE) if B.STATE.exists() else {}
        st["podcast_sample"] = {"week": week, "options": opts, "pick": None}
        write_json(B.STATE, st)
        return
    text = ("🎙️ <b>«اے آئی بیٹھک» — جمعہ کی قسط کا موضوع چنیں</b>\n\n" +
            "\n\n".join(f"<b>{i + 1}۔ {_h.escape(o['title'])}</b>\n{_h.escape(o['why'])}" for i, o in enumerate(opts)) +
            "\n\nنیچے نمبر دبائیں — یا اسی پیغام پر <b>Reply</b> کر کے اپنا موضوع لکھیں۔ "
            "جمعرات رات تک کچھ نہ چنا تو پہلا موضوع لیا جائے گا۔")
    mid = tg_call("sendMessage", chat_id=B.news_chat(), text=text, parse_mode="HTML",
                  reply_markup={"inline_keyboard": [[{"text": f"{i + 1}", "callback_data": f"ptopic:{week}|{i}"} for i in range(len(opts))]]}
                  )["message_id"]
    st = read_json(B.STATE) if B.STATE.exists() else {}
    st["podcast"] = {"week": week, "options": opts, "mid": mid, "pick": None}
    write_json(B.STATE, st)
    print("✅ موضوعات بھیج دیے:", [o["title"] for o in opts])


def on_pick(ns: dict, week: str, i: int, chat) -> None:
    """bulletin.poll سے: بٹن دبایا"""
    p = ns.get("podcast") or {}
    if p.get("week") != week or i >= len(p.get("options", [])):
        tg_call("sendMessage", chat_id=chat, text="یہ پرانی فہرست ہے — نئی فہرست بدھ کو آئے گی۔")
        return
    p["pick"] = i
    tg_call("sendMessage", chat_id=chat, text=f"🎙️ ٹھیک ہے — جمعہ کی «اے آئی بیٹھک» کا موضوع: {p['options'][i]['title']}")


def on_custom(ns: dict, text: str, chat) -> None:
    """bulletin.poll سے: موضوعات والے پیغام پر Reply"""
    ns["podcast"]["pick"] = text.strip()[:300]
    tg_call("sendMessage", chat_id=chat, text=f"🎙️ ٹھیک ہے — جمعہ کی «اے آئی بیٹھک» آپ کے موضوع پر ہوگی: {text.strip()[:200]}")


# ---------------- جمعہ: اسکرپٹ ----------------

SCRIPT_SYS = f"""آپ اردو پوڈکاسٹ «اے آئی بیٹھک» (فاروقی اے آئی نیوز) کے اسکرپٹ رائٹر ہیں۔ میزبان: سارہ (خاتون، عام ناظر کی طرح سوال اٹھاتی ہیں)
اور احمد (مرد، ٹیک کے ماہر، روزمرہ مثالوں سے آسان کر کے سمجھاتے ہیں)۔ دیے گئے موضوع پر تقریباً 5 منٹ کی مکمل قسط لکھیں۔
گفتگو قدرتی، دوستانہ، شائستہ اردو میں — چھوٹے جملے، ردِعمل («اچھا!»، «بالکل»)، ایک دوسرے کی بات آگے بڑھانا۔ خبر کا ماخذ بات چیت میں فطری انداز سے لیں («رائٹرز کے مطابق»)۔
ڈھانچہ: سارہ «السلام علیکم!» سے خوش آمدید کہیں، احمد کا تعارف اور موضوع ← خبر کیا ہے ← یہ کیسے کام کرتا ہے/کیوں اہم ← پاکستان اور عام آدمی پر اثر
← ایک فائدہ اور ایک خدشہ ← ناظرین کے لیے ایک عملی بات ← آخر میں سارہ کا مختصر خلاصہ، چینل سبسکرائب کرنے اور کمنٹ میں رائے دینے کی دعوت، «اللہ حافظ»۔
لمبائی: 13 تا 15 باریاں، کل 620 تا 720 الفاظ؛ ہر باری 25 تا 70 الفاظ (بہت چھوٹی باری نہیں)۔
{RULES} کوئی بریکٹ، ایموجی، ہدایت یا انگریزی حرف نہیں — صرف بولا جانے والا متن۔
صرف JSON: {{"title": "قسط کا عنوان، اردو، 4 تا 9 الفاظ", "lines": [{{"s": "Sarah" یا "Ahmed", "t": "متن"}}],
 "youtube_title": "یوٹیوب عنوان (اردو، زیادہ سے زیادہ 90 حروف)", "summary": "تفصیل کے 2 تا 3 جملے", "tags": ["12 تا 15 ٹیگ اردو/انگریزی"]}}"""


def script(topic: dict | str, feedback: str | None = None) -> dict:
    if isinstance(topic, dict):
        facts = topic["facts"]
        title = topic["title"]
    else:
        title, items = topic, _news(7)
        facts = [{k: it[k] for k in ("title", "source", "summary", "link")} for it in items[:120]]
    listing = "\n".join(f"[{i + 1}] {f['title']} — {f['source']} · {f['summary'][:400]}" for i, f in enumerate(facts))
    user = f"آج: {B.urdu_date()}\nموضوع: {title}\n\nمتعلقہ مستند خبریں (صرف انہی کے حقائق):\n{listing}"
    if feedback:
        user += f"\n\nمالک کی ہدایت: {feedback}"
    d = generate_json(SCRIPT_SYS, user)
    lines = []
    for l in d.get("lines", []):
        t = re.sub(r"[A-Za-z]", "", l.get("t") or "").strip()
        if t and l.get("s") in VOICES:
            lines.append({"s": l["s"], "t": t})
    if len(lines) < 8:
        raise RuntimeError(f"اسکرپٹ بہت مختصر ({len(lines)} باریاں)")
    d["lines"], d["topic"] = lines, title
    d["sources"] = [f for f in facts if isinstance(topic, dict)][:8]
    return d


# ---------------- آواز ----------------

def _gem(text: str, voice: str, keys: list[str]) -> dict | None:
    """ایک باری، ایک آواز۔ پہلی چابی کا روزانہ کوٹا ختم → دوسری۔ OTHER پر ایک بار دوبارہ۔"""
    other = 0
    while keys:
        r = requests.post(TTS_URL, params={"key": keys[0]}, timeout=240, json={
            "contents": [{"parts": [{"text": "Read the following Urdu text aloud in a warm, natural podcast tone:\n\n" + text}]}],
            "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {
                "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}}})
        if keys[0] == gemini_key():
            B.tts_note()
        c = (r.json().get("candidates") or [{}])[0] if r.ok else {}
        if c.get("content"):
            return c["content"]["parts"][0]["inlineData"]
        print("TTS", r.status_code, c.get("finishReason"), r.text[:140].replace("\n", " "))
        if r.status_code == 429:
            m = re.search(r'"retryDelay":\s*"(\d+)', r.text)
            if re.search(r"PerDay|per_day|limit: 0", r.text, flags=re.I) or not m:
                keys.pop(0)
                continue
            time.sleep(min(65, int(m.group(1)) + 3))
            continue
        other += 1
        if other > 1:
            return None
        time.sleep(8)
    return None


def voices(lines: list[dict], tmp: Path) -> tuple[list[Path], str]:
    keys = [k for k in (gemini_key() if B.tts_used() < B.TTS_LIMIT else None, os.environ.get("GEMINI_BACKUP_KEY", "").strip()) if k]
    out = []
    if os.environ.get("POD_TTS", "gemini") == "gemini" and keys:
        for i, l in enumerate(lines):
            if i:
                time.sleep(22)                                  # مفت حد: فی منٹ 3 درخواستیں
            part = _gem(l["t"], VOICES[l["s"]], keys)
            if not part:
                print(f"جیمنائی باری {i + 1} پر رک گیا — پوری گفتگو مائیکروسافٹ کی آوازوں میں")
                out = []
                break
            rate = int(re.search(r"rate=(\d+)", part.get("mimeType", "rate=24000")).group(1))
            raw = tmp / f"g{i}.raw.wav"
            with wave.open(str(raw), "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(base64.b64decode(part["data"]))
            out.append(B._trim(_norm(raw, tmp / f"g{i}.n.wav", pad=0.1), tmp / f"g{i}.wav"))
        if out:
            return out, "gemini"
        try:
            send_text(B.news_chat(), "ℹ️ آج کی «اے آئی بیٹھک» میں جیمنائی کی آواز پوری نہ بن سکی، اس لیے مائیکروسافٹ کی اردو آوازیں لگائی گئی ہیں۔", html=False)
        except Exception:
            pass
    import edge_tts
    for i, l in enumerate(lines):
        mp3 = tmp / f"e{i}.mp3"
        for k in range(3):
            try:
                asyncio.run(edge_tts.Communicate(l["t"], EDGE[l["s"]], rate="+0%").save(str(mp3)))
                break
            except Exception:
                time.sleep(4 * (k + 1))
        out.append(B._trim(_norm(mp3, tmp / f"e{i}.n.wav", pad=0.1), tmp / f"e{i}.wav"))
    return out, "edge"


# ---------------- ویڈیو ----------------

def build(d: dict, tmp: Path) -> tuple[Path, Path, str]:
    ws, engine = voices(d["lines"], tmp)
    parts, t = [], 0.0

    def add(p: Path):
        nonlocal t
        parts.append(p)
        t0, t = t, t + B._dur(p)
        return t0, t

    tune = tmp / "tune.wav"
    B._ff("-i", str(B.A / "headlines_logo.mp3"), "-t", "4.6", "-af", "volume=0.9,afade=t=out:st=3.6:d=1", "-ar", "44100", "-ac", "2",
          "-c:a", "pcm_s16le", str(tune))
    add(tune)
    open_end = t
    turns, caps = [], []
    for i, (l, w) in enumerate(zip(d["lines"], ws)):
        add(B._sil(0.4, tmp / f"s{i}.wav"))
        a, b = add(w)
        turns.append({"s": l["s"], "t0": round(a, 2), "t1": round(b, 2)})
        caps += [c | {"s": l["s"]} for c in _chunks(l["t"], a, b, max_words=9)]
    end_t = t + 0.5
    add(B._sil(4.5, tmp / "end.wav"))
    lst = tmp / "list.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    voice = tmp / "voice.wav"
    B._ff("-f", "concat", "-safe", "0", "-i", str(lst), "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(voice))
    dur = B._dur(voice)
    audio = tmp / "audio.wav"
    B._ff("-i", str(voice), "-stream_loop", "-1", "-i", str(B.A / "bed.m4a"), "-filter_complex",
          f"[1]volume=0.07,afade=t=in:st=3.5:d=1.5,afade=t=out:st={dur - 4:.2f}:d=4[b];"
          "[0][b]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-15:TP=-1.5[a]",
          "-map", "[a]", "-t", f"{dur:.2f}", "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(audio))
    nf = int(dur * FPS)
    energy = B._energy(voice, nf, [(x["t0"], x["t1"]) for x in turns])
    data = {"title": d["title"], "date": B.urdu_date(), "turns": turns, "caps": caps, "e": energy,
            "open_end": round(open_end, 2), "end_t": round(end_t, 2), "dur": round(dur, 2)}
    html = (B.A / "podcast.html").read_text(encoding="utf-8")
    html = (html.replace("__NQFONT__", B.FONT.as_uri()).replace("__LOGO__", B._b64(B.A / "logo_round.png", "image/png"))
            .replace("__NFDATA__", json.dumps(data, ensure_ascii=False)))
    page = tmp / "pod.html"
    page.write_text(html, encoding="utf-8")
    silent, thumb = tmp / "silent.mp4", tmp / "thumb.jpg"
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        br = B._launch(pw)
        pg = br.new_page(viewport={"width": 1920, "height": 1080})
        pg.goto(page.as_uri())
        pg.wait_for_function("document.title==='ready'", timeout=90000)
        pg.evaluate("thumb()")
        pg.screenshot(path=str(thumb), type="jpeg", quality=92)
        pg.evaluate("unthumb()")
        ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg", "-i", "-",
                               "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", str(silent)], stdin=subprocess.PIPE)
        for f in range(nf):
            pg.evaluate(f"render({f})")
            ff.stdin.write(pg.screenshot(type="jpeg", quality=86))
            if f % (FPS * 30) == 0:
                print(f"   فریم {f}/{nf}")
        ff.stdin.close()
        ff.wait()
        br.close()
    out = tmp / "podcast.mp4"
    B._ff("-i", str(silent), "-i", str(audio), "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out))
    return out, thumb, engine


def _topic(st: dict):
    p = st.get("podcast") or {}
    if p.get("week") != _week() or not p.get("options"):
        return None
    pick = p.get("pick")
    if isinstance(pick, str) and pick.strip():
        return pick.strip()
    return p["options"][pick if isinstance(pick, int) else 0]


def make(sample: bool = False, feedback: str | None = None) -> Path:
    st = read_json(B.STATE) if B.STATE.exists() else {}
    topic = _topic(st)
    if topic is None:                                   # بدھ کو فہرست نہ گئی ہو تو ابھی بنا کر پہلا موضوع
        suggest(send=not sample)
        st = read_json(B.STATE)
        topic = _topic({"podcast": st.get("podcast_sample")} if sample else st)
    d = script(topic, feedback)
    print("موضوع:", d["topic"], "| باریاں:", len(d["lines"]), "| الفاظ:", sum(len(l["t"].split()) for l in d["lines"]))
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        out, thumb, engine = build(d, tmp)
        import shutil
        final = B.ROOT / "podcast.mp4"
        shutil.copy(out, final)
        shutil.copy(thumb, B.ROOT / "podcast_thumb.jpg")
        write_json(B.ROOT / "state" / "podcast_last.json", d)
        mins = B._dur(final)
        print(f"✅ پوڈکاسٹ: {mins / 60:.1f} منٹ، آواز: {engine}")
        if sample:
            return final
        src = "\n".join(f"• {s['source']} — {s['link']}" for s in d.get("sources", []) if s.get("link"))
        sd = {"youtube_title": (d.get("youtube_title") or f"اے آئی بیٹھک: {d['title']}")[:95],
              "youtube_description": (f"🎙️ اے آئی بیٹھک — {d['title']}\n\n{d.get('summary', '')}\n\n"
                                      "ہر جمعہ: سارہ اور احمد کے ساتھ مصنوعی ذہانت کے ایک اہم موضوع پر آسان اردو میں گفتگو۔"
                                      + (f"\n\n🔗 ماخذ:\n{src}" if src else "")
                                      + "\n\nآوازیں: اے آئی · یہ سرمایہ کاری کا مشورہ نہیں۔\n\n#اے_آئی_بیٹھک #پوڈکاسٹ #AINews #فاروقی_اے_آئی_نیوز")[:4900],
              "tags": list(dict.fromkeys((d.get("tags") or []) + ["اے آئی بیٹھک", "اردو پوڈکاسٹ", "AI Podcast Urdu", "فاروقی اے آئی نیوز"]))}
        key = B._today() + "-p"
        d["stories"] = [{"headline": d["title"]}]
        vmid, mids = B.deliver(final, B.ROOT / "podcast_thumb.jpg", sd, d, key=key,
                               label=f"🎙️ اے آئی بیٹھک — «{d['title']}»" + ("" if engine == "gemini" else " (مائیکروسافٹ آوازیں)"))
        ytinfo = B._yt_upload(final, B.ROOT / "podcast_thumb.jpg", sd, playlist=PLAYLIST)
    st = read_json(B.STATE) if B.STATE.exists() else {}
    st.setdefault("days", {})[key] = {"status": "pending", "vmid": vmid, "mids": mids, "kind": "podcast", "voice": engine, **ytinfo}
    st.pop("redo_p", None)
    st["days"] = dict(sorted(st["days"].items())[-60:])
    write_json(B.STATE, st)
    return final


def tick(force: bool = False) -> None:
    st = read_json(B.STATE) if B.STATE.exists() else {}
    redo = st.get("redo_p")
    if redo:
        make(feedback=redo.get("feedback") if isinstance(redo, dict) else None)
        return
    if not force and dt.datetime.now(B.TZ).weekday() != POD_DAY:
        print("آج پوڈکاسٹ کا دن نہیں (جمعہ)")
        return
    if not force and (B._today() + "-p") in st.get("days", {}):
        print("آج کا پوڈکاسٹ بن چکا")
        return
    make()


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        if arg == "suggest":
            suggest()
        elif arg == "sample":
            make(sample=True)
        else:
            tick(force=arg == "force")
    except Exception as e:
        try:
            what = "موضوعات" if arg == "suggest" else "پوڈکاسٹ"
            send_text(B.news_chat(), f"⚠️ «اے آئی بیٹھک» کے {what} نہ بن سکے: {str(e)[:250]}", html=False)
        except Exception:
            pass
        raise
