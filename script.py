"""فاروقی اے آئی نیوز — روزانہ اے آئی کی تازہ ترین خبریں اردو میں

بہاؤ:
  ۱۔ معتبر ذرائع کی RSS فیڈز سے پچھلے 36 گھنٹوں کی اے آئی خبریں (کوئی چابی نہیں چاہیے)
  ۲۔ پہلے بھیجی جا چکی خبریں نکال دی جاتی ہیں (history.json)
  ۳۔ Gemini (مفت) سب سے اہم 6 خبریں چن کر اردو خلاصہ، تبصرہ + 60 سیکنڈ کا ویڈیو اسکرپٹ لکھتا ہے
     — صرف فیڈ میں موجود معلومات سے؛ ہر خبر کے ساتھ اصل ماخذ کا لنک
  ۴۔ نیوز اسٹوڈیو ویڈیو: اردو نیوز ریڈر (مرد آواز)، ہر خبر کی سلائیڈ، چلتی پٹی — studio.py
  ۵۔ بلیٹن + ویڈیو ٹیلیگرام پر (آپ کی چیٹ، اور چاہیں تو چینل)

    python script.py            # اصل رن (GitHub Actions)
    MOCK=1 python script.py     # آزمائش: نہ Gemini نہ ٹیلیگرام، صرف پرنٹ
"""
from __future__ import annotations

import html
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
HISTORY = ROOT / "history.json"
MOCK = os.environ.get("MOCK") == "1"
UA = {"User-Agent": "Mozilla/5.0 (compatible; farooqi-ai-news/1.0)"}

FEEDS = [
    ("TechCrunch", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("The Verge", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
    ("VentureBeat", "https://venturebeat.com/category/ai/feed/"),
    ("MIT Technology Review", "https://www.technologyreview.com/topic/artificial-intelligence/feed"),
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/technology-lab"),
    ("Wired", "https://www.wired.com/feed/tag/ai/latest/rss"),
    ("The Decoder", "https://the-decoder.com/feed/"),
    ("OpenAI", "https://openai.com/news/rss.xml"),
    ("Google AI", "https://blog.google/technology/ai/rss/"),
    ("Hugging Face", "https://huggingface.co/blog/feed.xml"),
    ("Google News", "https://news.google.com/rss/search?q=artificial+intelligence+when:1d&hl=en-US&gl=US&ceid=US:en"),
]
MODELS = ["gemini-2.5-flash", "gemini-flash-latest", "gemini-2.5-flash-lite"]
API = "https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"


def log(msg: str) -> None:
    print(f"[news] {msg}", flush=True)


# ---------------- ۱۔ خبریں جمع کرنا ----------------

def _text(el, *names) -> str:
    for child in el:
        if child.tag.split("}")[-1] in names and (child.text or "").strip():
            return " ".join(re.sub(r"<[^>]+>", " ", html.unescape(child.text)).split())
    return ""


def _link(el) -> str:
    for child in el:
        tag = child.tag.split("}")[-1]
        if tag == "link":
            return (child.text or child.get("href") or "").strip()
    return ""


def _when(el) -> datetime | None:
    raw = _text(el, "pubDate", "published", "updated")
    if not raw:
        return None
    try:
        d = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def fetch(hours: int = 36) -> list[dict]:
    if MOCK:
        return [{"source": "Mock", "title": f"Mock AI headline {i}", "summary": "Test summary.",
                 "link": f"https://example.com/{i}"} for i in range(8)]
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    items = []
    for name, url in FEEDS:
        try:
            r = requests.get(url, headers=UA, timeout=25)
            r.raise_for_status()
            root = ET.fromstring(r.content)
        except Exception as e:  # ایک فیڈ خراب ہو تو باقی چلتی رہیں
            log(f"{name}: چھوڑ دی ({e})")
            continue
        n = 0
        for el in root.iter():
            if el.tag.split("}")[-1] not in ("item", "entry"):
                continue
            title, link = _text(el, "title"), _link(el)
            when = _when(el)
            if not title or not link or (when and when < cutoff):
                continue
            items.append({"source": name, "title": title, "link": link,
                          "summary": _text(el, "description", "summary", "content")[:500]})
            n += 1
            if n >= 15:
                break
        log(f"{name}: {n} خبریں")
    return items


def _key(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()[:80]


def load_history() -> dict:
    return json.loads(HISTORY.read_text(encoding="utf-8")) if HISTORY.exists() else {"sent": []}


def fresh(items: list[dict], hist: dict) -> list[dict]:
    seen = set(hist.get("sent", []))
    out, keys = [], set()
    for it in items:
        k = _key(it["title"])
        if k in seen or k in keys:
            continue
        keys.add(k)
        out.append(it)
    return out


# ---------------- ۲۔ Gemini سے اردو بلیٹن ----------------

PROMPT = """آپ "فاروقی اے آئی نیوز" کے ایڈیٹر ہیں — ایک اردو چینل جو عام پاکستانی و ہندوستانی ناظرین کو
مصنوعی ذہانت (AI) کی تازہ ترین اور اہم خبریں آسان زبان میں سناتا ہے۔

نیچے آج کی خبروں کی فہرست ہے (نمبر، ذریعہ، سرخی، خلاصہ)۔ سختی سے ان اصولوں پر عمل کریں:
- پوری اے آئی کی دنیا سے (کمپنیاں، نئے ٹولز، تحقیق، پالیسی، روزگار، خطرات) سب سے اہم اور دلچسپ 6 خبریں چنیں؛ ایک ہی واقعے کی دو خبریں نہ لیں؛ موضوعات میں تنوع رکھیں
- صرف وہی بات لکھیں جو سرخی/خلاصے میں ہے۔ کوئی عدد، تاریخ، قیمت یا دعویٰ اپنی طرف سے نہ گھڑیں
- کمپنیوں اور پروڈکٹس کے نام انگریزی ہی میں رہنے دیں (OpenAI, Google, ChatGPT…)
- سادہ، صاف اردو؛ سنسنی خیزی نہیں

صرف یہ JSON واپس کریں:
{{
  "picks": [
    {{"n": خبر_کا_نمبر, "headline": "اردو سرخی (12 الفاظ تک)", "body": "2 سے 3 جملوں میں اردو خلاصہ: کیا ہوا", "comment": "ہمارا تبصرہ — ایک یا دو جملے: یہ خبر کیوں اہم ہے اور پاکستان/عام صارف پر کیا اثر پڑ سکتا ہے۔ رائے ہو، نئی معلومات یا اعداد نہ گھڑیں"}}
  ],
  "intro": "آغاز کا اعلان، ایک دو مختصر جملے، ‘السلام علیکم’ صرف ایک بار، جیسے: ‘السلام علیکم۔ فاروقی اے آئی نیوز میں خوش آمدید۔ آج کی تازہ ترین خبریں۔’",
  "outro": "اختتام، 1 سے 2 جملے: شکریہ، چینل فالو کرنے کی دعوت، اللہ حافظ",
  "title": "ویڈیو کا اردو عنوان (60 حروف تک)",
  "hashtags": "#AINews #مصنوعی_ذہانت سمیت 6 ہیش ٹیگ"
}}

آج کی خبریں:
{items}
"""

MOCK_OUT = {"picks": [{"n": i, "headline": f"آزمائشی سرخی {i}", "body": "آزمائشی خلاصہ۔", "comment": "آزمائشی تبصرہ۔"} for i in range(1, 7)],
            "intro": "السلام علیکم۔ فاروقی اے آئی نیوز میں خوش آمدید۔", "outro": "اللہ حافظ۔",
            "title": "آج کی اے آئی خبریں", "hashtags": "#AINews #مصنوعی_ذہانت"}


def _json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise
        return json.loads(m.group(0))


def write(items: list[dict]) -> dict:
    if MOCK:
        return MOCK_OUT
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise SystemExit("GEMINI_API_KEY نہیں ملی — Settings → Secrets → Actions میں ڈالیں")
    listing = "\n".join(f"{i}. [{it['source']}] {it['title']} — {it['summary'][:300]}"
                        for i, it in enumerate(items, 1))
    body = {"contents": [{"parts": [{"text": PROMPT.format(items=listing)}]}],
            "generationConfig": {"temperature": 0.3, "responseMimeType": "application/json"}}
    last = None
    for m in MODELS:
        for attempt in range(3):
            try:
                r = requests.post(API.format(m=m), json=body, timeout=180, headers={"x-goog-api-key": key})
                if r.status_code == 429 or r.status_code >= 500:
                    time.sleep(20 * (attempt + 1))
                    continue
                if r.status_code == 404:
                    break
                r.raise_for_status()
                parts = r.json()["candidates"][0]["content"]["parts"]
                out = _json("".join(p.get("text", "") for p in parts))
                log(f"Gemini ({m}) نے بلیٹن لکھا")
                return out
            except (requests.RequestException, KeyError, ValueError) as e:
                last = e
                time.sleep(5)
    raise RuntimeError(f"Gemini جواب نہ دے سکا: {last}")


# ---------------- ۳۔ ٹیلیگرام ----------------

URDU = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def bulletin(out: dict, items: list[dict]) -> str:
    today = datetime.now(timezone(timedelta(hours=3))).strftime("%d-%m-%Y").translate(URDU)
    lines = [f"🤖 <b>فاروقی اے آئی نیوز</b> — {today}", ""]
    for i, p in enumerate(out.get("picks", [])[:6], 1):
        n = int(p.get("n", 0))
        if not 1 <= n <= len(items):
            continue
        src = items[n - 1]
        lines += [f"<b>{str(i).translate(URDU)}۔ {html.escape(p['headline'])}</b>",
                  html.escape(p["body"]),
                  *([f"💬 <i>{html.escape(p['comment'])}</i>"] if p.get("comment") else []),
                  f'🔗 <a href="{html.escape(src["link"])}">{html.escape(src["source"])}</a>', ""]
    lines.append(html.escape(out.get("hashtags", "")))
    return "\n".join(lines)


def send(text: str, chat: str) -> None:
    if MOCK:
        print(text, "\n")
        return
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN نہیں ملا — Settings → Secrets → Actions میں ڈالیں")
    for chunk in [text[i:i + 4000] for i in range(0, len(text), 4000)]:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", timeout=60, json={
            "chat_id": chat, "text": chunk, "parse_mode": "HTML", "disable_web_page_preview": True})
        if not r.json().get("ok"):
            raise RuntimeError(f"ٹیلیگرام: {r.json().get('description')}")


def send_video(path: Path, caption: str, chat: str) -> None:
    if MOCK:
        print(f"[video] {path} ({path.stat().st_size // 1024} KB) → {chat}")
        return
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    with open(path, "rb") as f:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendVideo", timeout=900,
                          data={"chat_id": chat, "caption": caption, "supports_streaming": "true",
                                "width": 1920, "height": 1080}, files={"video": (path.name, f, "video/mp4")})
    if not r.json().get("ok"):
        raise RuntimeError(f"ٹیلیگرام ویڈیو: {r.json().get('description')}")


def main() -> None:
    hist = load_history()
    items = fresh(fetch(), hist)
    log(f"نئی خبریں: {len(items)}")
    if len(items) < 3:
        log("آج کافی نئی خبریں نہیں — کچھ نہیں بھیجا")
        return
    items = items[:40]
    out = write(items)
    me = os.environ.get("TELEGRAM_CHAT_ID", "")
    channel = os.environ.get("TELEGRAM_CHANNEL", "")
    text = bulletin(out, items)
    if not me and not channel and not MOCK:
        raise SystemExit("TELEGRAM_CHAT_ID (یا TELEGRAM_CHANNEL) Secret میں ڈالیں")
    if channel:
        send(text, channel)
    if me:
        send(text, me)
    # نیوز اسٹوڈیو ویڈیو (اردو نیوز ریڈر کی آواز کے ساتھ)
    if os.environ.get("MAKE_VIDEO", "1") == "1":
        import studio
        now = datetime.now(timezone(timedelta(hours=3)))
        months = ["جنوری", "فروری", "مارچ", "اپریل", "مئی", "جون", "جولائی", "اگست", "ستمبر", "اکتوبر", "نومبر", "دسمبر"]
        today = f"{str(now.day).translate(URDU)} {months[now.month - 1]} {str(now.year).translate(URDU)}"
        video = studio.render(out, items, today, ROOT / "news_video.mp4")
        cap = (f"🎬 {out.get('title', 'آج کی اے آئی خبریں')}\n\n{out.get('hashtags', '')}")[:1000]
        for c in [x for x in (channel, me) if x]:
            send_video(video, cap, c)
        if me:
            send("📋 <b>یوٹیوب / فیس بک کے لیے</b>\n\n<b>عنوان:</b>\n" + html.escape(out.get("title", "")) +
                 "\n\n<b>تفصیل:</b>\n" + html.escape(re.sub(r"<[^>]+>", "", text)), me)
        if not MOCK:
            video.unlink(missing_ok=True)
    used = [items[int(p["n"]) - 1]["title"] for p in out.get("picks", []) if 1 <= int(p.get("n", 0)) <= len(items)]
    hist["sent"] = (hist.get("sent", []) + [_key(t) for t in used])[-500:]
    if not MOCK:
        HISTORY.write_text(json.dumps(hist, ensure_ascii=False, indent=1), encoding="utf-8")
    log("بھیج دیا ✅")


if __name__ == "__main__":
    main()
