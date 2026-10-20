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
MODELS = ["gemini-3.8-flash", "gemini-flash-latest", "gemini-3.5-flash-lite", "gemini-2.5-flash", "gemini-2.5-flash-lite"]


def available_models(key: str, want: str) -> list[str]:
    """اس چابی پر جو ماڈل واقعی چلتے ہیں — Google ماڈل بدلتا رہتا ہے، اس لیے خود پوچھ لیں"""
    try:
        r = requests.get("https://generativelanguage.googleapis.com/v1beta/models?pageSize=200",
                         headers={"x-goog-api-key": key}, timeout=30)
        names = [m["name"].split("/")[-1] for m in r.json().get("models", [])
                 if "generateContent" in m.get("supportedGenerationMethods", [])]
    except Exception:
        return []
    if want == "tts":
        return sorted([n for n in names if "tts" in n], key=lambda n: ("pro" in n, n), reverse=False)
    flash = [n for n in names if "flash" in n and not any(x in n for x in ("tts", "image", "audio", "live", "embed"))]
    def rank(n):
        v = re.search(r"(\d+(?:\.\d+)?)", n)
        return (-(float(v.group(1)) if v else 0), "lite" in n, "preview" in n or "exp" in n, n)
    return sorted(flash, key=rank)
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
- پوری ویڈیو تقریباً 3 منٹ کی ہو: چھ خبروں کے سرخی + خلاصہ + تبصرہ ملا کر کل تقریباً 330 الفاظ (ہر خلاصہ 2 مختصر جملے، ہر تبصرہ 1 جملہ)

صرف یہ JSON واپس کریں:
{{
  "picks": [
    {{"n": خبر_کا_نمبر, "headline": "اردو سرخی (12 الفاظ تک)", "body": "2 سے 3 جملوں میں اردو خلاصہ: کیا ہوا", "comment": "ہمارا تبصرہ — ایک یا دو جملے: یہ خبر کیوں اہم ہے اور پاکستان/عام صارف پر کیا اثر پڑ سکتا ہے۔ رائے ہو، نئی معلومات یا اعداد نہ گھڑیں"}}
  ],
  "intro": "آغاز کا اعلان، ایک دو مختصر جملے، ‘السلام علیکم’ صرف ایک بار، جیسے: ‘السلام علیکم۔ فاروقی اے آئی نیوز میں خوش آمدید۔ آج کی تازہ ترین خبریں۔’",
  "outro": "اختتام، 1 سے 2 جملے: شکریہ، چینل فالو کرنے کی دعوت، اللہ حافظ",
  "title": "یوٹیوب SEO عنوان، 70 حروف تک: سب سے بڑی خبر کا اہم انگریزی نام (مثلاً OpenAI / ChatGPT) شروع میں، پھر اردو؛ آخر میں ' | اے آئی نیوز اردو'۔ کلک بیٹ یا جھوٹ نہیں",
  "title_alts": ["متبادل عنوان 1", "متبادل عنوان 2"],
  "hook": "تفصیل کی پہلی 2 لائنیں (150 حروف تک): آج کی سب سے اہم خبریں، اہم کی ورڈز کے ساتھ — یہی سرچ میں نظر آتی ہیں",
  "summary_en": "One English sentence summarising today's top AI stories, with the key names (for English search)",
  "tags": ["15 سے 20 ٹیگ: اردو، انگریزی اور رومن اردو/ہندی ملا کر؛ آج کی خبروں کے نام (کمپنی/ٹول) + عام ٹیگ جیسے AI news Urdu, AI news in Hindi, مصنوعی ذہانت, artificial intelligence, ChatGPT; کل 450 حروف سے کم"],
  "hashtags": "صرف 3 سے 5 ہیش ٹیگ، پہلا #AINews (یوٹیوب پہلے 3 عنوان کے اوپر دکھاتا ہے)",
  "thumbnail_text": "تھمب نیل پر لکھنے کے لیے 3 سے 5 اردو الفاظ، دلچسپ",
  "pinned_comment": "پن کرنے کے لیے ایک کمنٹ: ناظرین سے آج کی خبروں پر ایک سوال پوچھیں تاکہ وہ جواب دیں",
  "fb_caption": "فیس بک پوسٹ کے لیے 2 سے 3 لائن اردو کیپشن"
}}

آج کی خبریں:
{items}
"""

MOCK_OUT = {"picks": [{"n": i, "headline": f"آزمائشی سرخی {i}", "body": "آزمائشی خلاصہ۔", "comment": "آزمائشی تبصرہ۔"} for i in range(1, 7)],
            "intro": "السلام علیکم۔ فاروقی اے آئی نیوز میں خوش آمدید۔", "outro": "اللہ حافظ۔",
            "title": "آج کی اے آئی خبریں", "hashtags": "#AINews #مصنوعی_ذہانت",
            "title_alts": ["متبادل ۱", "متبادل ۲"], "hook": "آزمائشی ہک۔", "summary_en": "Mock summary.",
            "tags": ["AI news Urdu", "مصنوعی ذہانت"], "thumbnail_text": "آج کی بڑی خبر",
            "pinned_comment": "آپ کی رائے؟", "fb_caption": "آزمائشی کیپشن۔"}


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
    found = available_models(key, "text")
    log(f"دستیاب ماڈل: {', '.join(found[:6]) or '—'}")
    for m in list(dict.fromkeys(found[:4] + MODELS)):
        for attempt in range(3):
            try:
                r = requests.post(API.format(m=m), json=body, timeout=180, headers={"x-goog-api-key": key})
                if r.status_code != 200:
                    last = f"{m} → HTTP {r.status_code}: {r.text[:400]}"
                    log(last)
                if r.status_code in (400, 401, 403):
                    raise SystemExit(f"Gemini کی چابی میں مسئلہ (غلط/بند key؟): {last}")
                if r.status_code == 429 or r.status_code >= 500:
                    if "PerDay" in r.text or "limit: 0" in r.text:
                        break                       # اس ماڈل کا روزانہ کوٹہ ختم — اگلا ماڈل
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


def _ts(sec: float) -> str:
    sec = int(sec)
    return f"{sec // 60}:{sec % 60:02d}"


def seo(out: dict, items: list[dict]) -> list[str]:
    """یوٹیوب / فیس بک کے لیے مکمل SEO پیکج — ہر حصہ الگ پیغام تاکہ آسانی سے کاپی ہو"""
    picks = [p for p in out.get("picks", []) if 1 <= int(p.get("n", 0)) <= len(items)]
    tags = out.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",")]
    base = ["AI news Urdu", "AI news in Urdu", "AI news Hindi", "مصنوعی ذہانت", "اے آئی نیوز",
            "artificial intelligence", "Farooqi AI News", "tech news Urdu"]
    seen, tag_list = set(), []
    for t in [*tags, *base]:
        t = t.strip().lstrip("#")
        if t and t.lower() not in seen and len(", ".join(tag_list + [t])) <= 480:
            seen.add(t.lower()); tag_list.append(t)
    hashtags = out.get("hashtags", "#AINews")
    desc = [out.get("hook", ""), ""]
    chapters = out.get("_chapters") or []
    if len(chapters) >= 3:
        desc += ["⏱️ ابواب (Chapters):", *[f"{_ts(t)} {lbl}" for t, lbl in chapters], ""]
    desc += ["📰 آج کی خبریں:"]
    for p in picks:
        desc.append(f"• {p['headline']}")
    desc += ["", "🔗 ذرائع:"]
    for p in picks:
        it = items[int(p["n"]) - 1]
        desc.append(f"{it['source']}: {it['link']}")
    desc += ["", out.get("summary_en", ""), "",
             "فاروقی اے آئی نیوز — مصنوعی ذہانت کی دنیا کی روزانہ خبریں، آسان اردو میں۔ "
             "روزانہ نئی ویڈیو کے لیے چینل کو سبسکرائب کریں اور گھنٹی کا بٹن دبائیں 🔔", "", hashtags]
    e = html.escape
    alts = "\n".join(f"• {e(a)}" for a in out.get("title_alts", []) if a)
    return [
        "📋 <b>یوٹیوب SEO — مکمل پیکج</b>\n\n"
        f"<b>① عنوان (Title):</b>\n<code>{e(out.get('title', ''))}</code>"
        + (f"\n\n<b>متبادل عنوان:</b>\n{alts}" if alts else "")
        + f"\n\n<b>② تھمب نیل کا متن:</b>\n{e(out.get('thumbnail_text', ''))}"
        "\n\n<b>③ سیٹنگز:</b>\nCategory: <b>News &amp; Politics</b> · Language: <b>Urdu</b> · "
        "Made for kids: <b>No</b> · Playlist: <b>روزانہ اے آئی خبریں</b>",
        "<b>④ تفصیل (Description) — پوری کاپی کریں:</b>\n\n<code>" + e("\n".join(desc)) + "</code>",
        "<b>⑤ ٹیگز (Tags) — پوری لائن کاپی کر کے Tags خانے میں:</b>\n\n<code>" + e(", ".join(tag_list)) + "</code>",
        f"<b>⑥ پن کمنٹ:</b>\n<code>{e(out.get('pinned_comment', ''))}</code>\n\n"
        f"<b>⑦ فیس بک کیپشن:</b>\n<code>{e(out.get('fb_caption', ''))}\n\n{e(hashtags)}</code>",
    ]


def find_chat_id() -> str:
    """TELEGRAM_CHAT_ID نہ ہو تو: بوٹ کو جس نے آخری پیغام بھیجا، اسی کی چیٹ (ایک بار مل جائے تو history.json میں یاد)"""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN نہیں ملا — Settings → Secrets → Actions میں ڈالیں")
    r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=30).json()
    if not r.get("ok"):
        raise SystemExit(f"ٹیلیگرام بوٹ ٹوکن غلط ہے: {r.get('description')}")
    chats = [u["message"]["chat"]["id"] for u in r.get("result", [])
             if u.get("message", {}).get("chat", {}).get("type") == "private"]
    if not chats:
        me_ = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=30).json().get("result", {})
        wh = requests.get(f"https://api.telegram.org/bot{token}/getWebhookInfo", timeout=30).json().get("result", {})
        log(f"یہ ٹوکن اس بوٹ کا ہے: @{me_.get('username')} ({me_.get('first_name')}); webhook: {wh.get('url') or 'none'}")
        raise SystemExit("بوٹ کو ابھی کسی نے پیغام نہیں بھیجا — ٹیلیگرام میں ai_news_bot کھول کر 'hi' بھیجیں، پھر دوبارہ چلائیں")
    log("ٹیلیگرام چیٹ مل گئی ✅")
    return str(chats[-1])


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
    # ٹیلیگرام پہلے چیک — تاکہ Gemini کا کوٹہ ضائع نہ ہو
    me = os.environ.get("TELEGRAM_CHAT_ID", "").strip() or str(hist.get("chat_id", ""))
    if not me and not MOCK:
        me = find_chat_id()
        if me:
            hist["chat_id"] = me
    channel = os.environ.get("TELEGRAM_CHANNEL", "")
    out = write(items)
    # ویڈیو تقریباً 3 منٹ کی رہے: الفاظ زیادہ ہوں تو آخری خبریں نکال دیں (کم از کم 4)
    def words(p): return len(f"{p.get('headline','')} {p.get('body','')} {p.get('comment','')}".split())
    picks = out.get("picks", [])[:6]
    while len(picks) > 4 and sum(words(p) for p in picks) > 380:
        picks.pop()
    out["picks"] = picks
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
            for msg in seo(out, items):
                send(msg, me)
        if not MOCK:
            video.unlink(missing_ok=True)
    used = [items[int(p["n"]) - 1]["title"] for p in out.get("picks", []) if 1 <= int(p.get("n", 0)) <= len(items)]
    hist["sent"] = (hist.get("sent", []) + [_key(t) for t in used])[-500:]
    if not MOCK:
        HISTORY.write_text(json.dumps(hist, ensure_ascii=False, indent=1), encoding="utf-8")
    log("بھیج دیا ✅")


if __name__ == "__main__":
    main()
