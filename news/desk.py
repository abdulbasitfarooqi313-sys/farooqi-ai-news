"""«روزنامچہ فاروقی» — تینوں چینلوں کا روزانہ مواد مرکز (Beyond Tahir والے Content HQ کا مفت متبادل)

ہر شعبے (news / toolscape / nawa) کے لیے روز صبح:
  ٹرینڈنگ ماخذ (RSS) + مقابل چینلوں کی تازہ ویڈیوز (یوٹیوب RSS) + ہک بینک + انداز نامہ
  → جیمنائی کی ایک درخواست → 10 ٹرینڈنگ موضوعات، 3 مکمل پیکج (لمبی ویڈیو، 2 شارٹس، کیروسل،
    ایکس/فیس بک/انسٹا/لنکڈ اِن، مضمون، وائرل امکان)، ہک کے انداز
  → desk/<niche>.html + desk/index.json  (نوائے فاروقی کا بوٹ اسے نجی بلاگ farooqidailydesk پر شائع کرتا ہے)

    python -m news.desk            # تینوں
    python -m news.desk nawa       # ایک
"""
from __future__ import annotations

import datetime as dt
import html as H
import json
import re
import sys
import traceback
import xml.etree.ElementTree as ET

import requests

import time

from .base import FALLBACKS, GEMINI_MODEL, ROOT, gemini_key, parse_json
from . import insight

OUT = ROOT / "desk"
TZ = dt.timezone(dt.timedelta(hours=3))
UA = {"User-Agent": "Mozilla/5.0 (FarooqiDailyDesk RSS reader)"}

NICHES = {
    "news": {
        "name": "فاروقی اے آئی نیوز", "label": "AI News", "color": "#0a1550", "color2": "#e2b84f", "dark": "#050b33", "rtl": True, "lang": "اردو",
        "about": "مصنوعی ذہانت کی خبروں کا اردو بلیٹن (پاکستان/ہندوستان کے ناظرین، پیر بدھ ہفتہ)",
        "feeds": [
            "https://news.google.com/rss/search?q=%22artificial+intelligence%22+OR+OpenAI+OR+Gemini+OR+Anthropic+when:1d&hl=en-US&gl=US&ceid=US:en",
            "https://techcrunch.com/category/artificial-intelligence/feed/",
            "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
            "https://hnrss.org/newest?q=AI&points=150",
            "https://www.reddit.com/r/artificial/top/.rss?t=day",
            "https://news.google.com/rss/search?q=AI+when:2d&hl=ur&gl=PK&ceid=PK:ur",
        ],
    },
    "toolscape": {
        "name": "Toolscape", "label": "Toolscape", "color": "#0e7490", "color2": "#22d3ee", "dark": "#0b1220", "rtl": False, "lang": "English",
        "about": "English faceless YouTube channel: step-by-step AI tool tutorials and tool lists for beginners in US/UK/Canada",
        "feeds": [
            "https://www.producthunt.com/feed",
            "https://hnrss.org/newest?q=AI+tool&points=100",
            "https://news.google.com/rss/search?q=new+AI+tool+when:3d&hl=en-US&gl=US&ceid=US:en",
            "https://www.reddit.com/r/ChatGPT/top/.rss?t=day",
            "https://www.reddit.com/r/AItools/top/.rss?t=week",
        ],
    },
    "nawa": {
        "name": "نوائے فاروقی", "label": "Nawa-e-Farooqi", "color": "#1d5c46", "color2": "#b08d3c", "dark": "#0f2f24", "rtl": True, "lang": "اردو",
        "about": ("قرآن کی اردو تفسیر کا دینی چینل (ترجمہ شیخ الہندؒ، تفسیرِ عثمانی کی روشنی میں) — رکوع وار سلسلہ، "
                  "شارٹس، تلاوت ویڈیو، لمبی ویڈیو، بلاگ۔ موضوعات صرف قرآن و تفسیر کی حد میں، کوئی نیا دینی دعویٰ نہیں"),
        "feeds": [
            "https://news.google.com/rss/search?q=%D9%82%D8%B1%D8%A2%D9%86+when:7d&hl=ur&gl=PK&ceid=PK:ur",
            "https://news.google.com/rss/search?q=Quran+OR+Islamic+when:3d&hl=en-PK&gl=PK&ceid=PK:en",
        ],
    },
}

SYSTEM = """You are the head of content strategy for the YouTube channel described below. Every morning you prepare
the team's "daily desk": what is trending, what competitors did, and ready-to-produce content packages.
Write ALL text values in {lang}{script}. Be honest and specific; never invent facts, numbers or quotes —
use only what the trending items and competitor titles show. Viral scores are strict, realistic estimates: most ideas
score 25-60; above 75 only when a topic is exploding AND our angle clearly beats the competitors; never give all packages 80+.
{extra}

Channel: {name} — {about}

Return ONLY this JSON:
{{"summary": "2 sentences: the big picture today for this channel",
 "topics": [10 items, most promising first: {{"title": "topic", "why": "1 sentence why it is hot / useful now",
            "trend": 1-10, "sources": ["where it is being discussed: site or competitor channel names"]}}],
 "packages": [3 items for the top 3 topics: {{
    "topic": "topic",
    "competitors": "1-2 sentences: how competitors covered it (name them) and what they missed",
    "angle": "1 sentence: our different / better angle",
    "viral": {{"score": 0-100, "why": "1-2 sentences"}},
    "long": {{"title": "YouTube title", "thumb": "2-5 word thumbnail text", "hook": "first 2 spoken sentences",
             "outline": ["5-7 section points"]}},
    "shorts": [2 items: {{"title": "short title", "hook": "first sentence (under 3 seconds)",
                "script": "40-60 second script", "cta": "closing line"}}],
    "carousel": {{"title": "cover slide", "slides": ["5-7 short slide texts"]}},
    "posts": {{"x": ["2 posts, under 260 chars each"], "facebook": "post", "instagram": "caption + hashtags",
              "linkedin": "post"}},
    "article": {{"title": "blog article title", "outline": ["4-6 headings"]}}}}],
 "hook_patterns": [5 items: {{"pattern": "a hook pattern that worked for competitors (from the view counts)",
                   "example": "the same pattern written for our channel"}}]}}"""

EXTRA = {
    "nawa": ("Religious channel rules: respectful and dignified; no sensationalism, fear-mongering, 'shocking secret' "
             "style, sectarian or controversial angles. Topics must be Quran verses/themes and tafseer lessons "
             "(Islamic calendar occasions, life lessons from specific surahs). Never invent hadith or rulings."),
    "news": "Urdu script only (English names written in Urdu script, e.g. اوپن اے آئی). Serious TV-news tone.",
    "toolscape": "Prefer tools with a free plan that can be demonstrated on screen step by step.",
}


def _items(url: str, limit: int = 20) -> list[str]:
    try:
        r = requests.get(url, headers=UA, timeout=25)
        root = ET.fromstring(r.content)
    except Exception as e:
        print(f"feed skipped {url[:60]}: {e}")
        return []
    out = []
    for el in root.iter():
        if el.tag.split("}")[-1] in ("item", "entry"):
            t = next((c.text for c in el if c.tag.split("}")[-1] == "title" and c.text), "")
            if t:
                out.append(" ".join(t.split()))
    src = re.sub(r"^https?://(www\.)?([^/]+).*", r"\2", url)
    return [f"[{src}] {t}" for t in out[:limit]]


LOG: list[str] = []
DESK_MODELS = ["gemini-3.6-flash", "gemini-3.5-flash-lite", "gemini-flash-latest", GEMINI_MODEL]


def note(msg: str) -> None:
    LOG.append(f"{time.strftime('%H:%M:%S')} {msg}")
    print(LOG[-1], flush=True)


def ask(system: str, user: str) -> str:
    """جیمنائی — ہر کوشش کا وقت اور نتیجہ لاگ میں؛ لمبے انتظار نہیں"""
    body = {"systemInstruction": {"parts": [{"text": system}]}, "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0.4, "maxOutputTokens": 60000, "responseMimeType": "application/json"}}
    # بلیٹن کے لیے بڑا ماڈل بچا رہے: روزنامچہ پہلے ہلکے ماڈلوں سے
    for model in DESK_MODELS:
        for attempt in range(2):
            t = time.time()
            try:
                r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                                  json=body, headers={"x-goog-api-key": gemini_key()}, timeout=240)
            except requests.RequestException as e:
                note(f"{model}: {type(e).__name__} after {time.time() - t:.0f}s")
                continue
            note(f"{model}: HTTP {r.status_code} in {time.time() - t:.0f}s")
            if r.ok:
                c = r.json().get("candidates", [{}])[0]
                txt = "".join(p.get("text", "") for p in c.get("content", {}).get("parts", []))
                note(f"   finish={c.get('finishReason')} chars={len(txt)}")
                if txt:
                    return txt
            elif r.status_code == 429:
                note("   " + r.text[:200].replace("\n", " "))
                time.sleep(20)
            elif r.status_code in (404, 400):
                note("   " + r.text[:200].replace("\n", " "))
                break
            else:
                time.sleep(10)
    raise RuntimeError("Gemini: no answer")


def build(niche: str) -> dict:
    cfg = NICHES[niche]
    note(f"{niche}: start")
    data = insight.gather(niche)
    heads = [h for u in cfg["feeds"] for h in _items(u)]
    note(f"{niche}: {len(data[0])} competitor videos, {len(heads)} trending items")
    user = (f"Today: {dt.datetime.now(TZ):%A %d %B %Y}\n\nTRENDING ITEMS (last 1-3 days):\n" + "\n".join(heads[:120])
            + "\n\n" + insight.brief(niche, data=data) + "\n\nCHANNEL STYLE GUIDE:\n" + insight.style_guide(niche))
    system = SYSTEM.format(lang=cfg["lang"], script=" (Urdu script, never Roman Urdu)" if cfg["rtl"] else "",
                           extra=EXTRA.get(niche, ""), name=cfg["name"], about=cfg["about"])
    d, last = None, None
    for i in range(2):          # لمبا جواب: بڑی حد (اردو میں 8 ہزار ٹوکن کم پڑتے ہیں)
        try:
            d = parse_json(ask(system, user + ("" if not i else "\n\nIMPORTANT: return complete, valid JSON only; keep texts shorter.")))
            break
        except ValueError as e:
            last = e
            note(f"desk {niche}: JSON error ({e})")
    if d is None:
        raise ValueError(f"desk {niche}: {last}")
    d["_competitors"] = data[0][:15]
    d["_bank"] = data[1][:15]
    return d


# ---------------- HTML ----------------

CSS = """<style>
.dd{--a:#1d5c46;--ink:#16231d;--muted:#5f6b66;--line:#e3e8e4;--soft:#f4f6f3;--gold:#b08d3c;--goldl:#f6efdc;--dk:#0f2f24;
 font-family:'Jameel Noori Web','Jameel Noori Nastaleeq','Noto Nastaliq Urdu',serif;color:var(--ink);line-height:2;font-size:16px}
.dd.ltr{font-family:'Inter',system-ui,-apple-system,'Segoe UI',sans-serif;line-height:1.6}
.dd *{box-sizing:border-box}
.dd .hero{background:linear-gradient(135deg,var(--dk),var(--a));border-bottom:4px solid var(--gold);color:#fff;border-radius:14px;padding:16px 18px;margin:6px 0 16px}
.dd .hero p{margin:0 0 12px;font-size:16px;opacity:.95}
.dd .tiles{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}
.dd .tile{background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.18);border-radius:10px;padding:8px 10px;text-align:center}
.dd .tile b{display:block;font-family:'Inter',system-ui,sans-serif;font-size:22px;line-height:1.3}
.dd .tile span{font-size:12.5px;opacity:.85}
.dd h2{font-size:19px;margin:26px 0 10px;padding:4px 14px;border-inline-start:5px solid var(--gold);background:var(--soft);border-radius:8px;color:var(--a)}
.dd h3{font-size:17px;margin:16px 0 6px;color:var(--a)}
.dd .tbl{overflow-x:auto;border:1px solid var(--line);border-radius:12px}
.dd table{width:100%;border-collapse:collapse;font-size:14.5px}
.dd td,.dd th{border-bottom:1px solid var(--line);padding:7px 10px;vertical-align:top;text-align:start}
.dd tr:last-child td{border-bottom:0}
.dd th{background:var(--soft);font-weight:700;color:var(--muted);font-size:13px}
.dd .num{font-family:'Inter',system-ui,sans-serif;font-weight:700;color:var(--a)}
.dd .meter{display:block;width:70px;height:7px;border-radius:5px;background:var(--line);overflow:hidden;margin-top:4px}
.dd .meter i{display:block;height:100%;background:linear-gradient(90deg,var(--a),var(--gold))}
.dd .pk{border:1px solid var(--line);border-radius:14px;padding:4px 16px 14px;margin:14px 0;background:#fff;border-top:4px solid var(--a)}
.dd .pk-h{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap}
.dd .pk-h h2{margin:12px 0 6px;background:none;border:0;padding:0;font-size:19px}
.dd .score{font-family:'Inter',system-ui,sans-serif;font-weight:800;background:var(--a);color:var(--gold);border-radius:999px;padding:3px 14px;font-size:14px;white-space:nowrap}
.dd .why{background:var(--soft);border-radius:10px;padding:8px 12px;margin:6px 0}
.dd .copy{white-space:pre-wrap;background:#fbfaf6;border:1px dashed #d8ccaa;border-radius:10px;padding:8px 12px;margin:6px 0;font-size:15px;user-select:all}
.dd .muted{color:var(--muted);font-size:13px}
.dd details{margin:6px 0;border:1px solid var(--line);border-radius:10px;padding:4px 12px;background:#fff}
.dd summary{cursor:pointer;font-weight:700;color:var(--a);padding:2px 0}
.dd ol,.dd ul{margin:6px 0;padding-inline-start:24px}
.dd a{color:#1d4ed8}
@media(max-width:640px){.dd .tiles{grid-template-columns:repeat(2,1fr)}.dd{font-size:15px}}
</style>"""


def _e(x) -> str:
    return H.escape(str(x or ""))


def _copy(x) -> str:
    return f'<div class="copy">{_e(x)}</div>' if x else ""


def render(niche: str, d: dict, day: str) -> str:
    cfg = NICHES[niche]
    rtl = cfg["rtl"]
    L = (lambda ur, en: ur if rtl else en)
    pk = d.get("packages", [])[:3]
    top = max([int(p.get("viral", {}).get("score") or 0) for p in pk if str(p.get("viral", {}).get("score", "")).isdigit()] or [0])
    o = [CSS, f'<div class="dd{"" if rtl else " ltr"}" dir="{"rtl" if rtl else "ltr"}" style="--a:{cfg["color"]};--gold:{cfg["color2"]};--dk:{cfg["dark"]}">',
         f'<div class="hero"><p>{_e(d.get("summary"))}</p><div class="tiles">'
         f'<div class="tile"><b>{len(d.get("topics", [])[:10])}</b><span>{L("ٹرینڈنگ موضوعات", "trending topics")}</span></div>'
         f'<div class="tile"><b>{len(pk)}</b><span>{L("تیار پیکج", "ready packages")}</span></div>'
         f'<div class="tile"><b>{top}%</b><span>{L("سب سے زیادہ وائرل امکان", "best viral chance")}</span></div>'
         f'<div class="tile"><b>{len(d.get("_competitors") or [])}</b><span>{L("مقابل ویڈیوز دیکھی گئیں", "competitor videos read")}</span></div>'
         '</div></div>',
         f'<h2>🔥 {L("آج کے 10 ٹرینڈنگ موضوعات", "Top 10 trending topics today")}</h2>',
         f'<div class="tbl"><table><tr><th>#</th><th>{L("موضوع", "Topic")}</th><th>{L("ٹرینڈ", "Trend")}</th><th>{L("کیوں / کہاں", "Why / where")}</th></tr>']
    for i, t in enumerate(d.get("topics", [])[:10], 1):
        tr = max(1, min(10, int(t.get("trend")))) if str(t.get("trend", "")).isdigit() else 5
        o.append(f'<tr><td class="num">{i}</td><td><b>{_e(t.get("title"))}</b></td>'
                 f'<td><span class="num">{tr}/10</span><span class="meter"><i style="width:{tr * 10}%"></i></span></td>'
                 f'<td>{_e(t.get("why"))}<br><span class="muted">{_e(", ".join(t.get("sources") or []))}</span></td></tr>')
    o.append("</table></div>")
    for i, p in enumerate(d.get("packages", [])[:3], 1):
        v, lg = p.get("viral") or {}, p.get("long") or {}
        o.append(f'<div class="pk"><div class="pk-h"><h2>📦 {L("پیکج", "Package")} {i}: {_e(p.get("topic"))}</h2>'
                 f'<span class="score">🔥 {_e(v.get("score", "?"))}/100</span></div>'
                 f'<div class="why">{_e(v.get("why"))}</div><p><b>{L("مقابلین", "Competitors")}:</b> {_e(p.get("competitors"))}</p>'
                 f'<p><b>{L("ہمارا زاویہ", "Our angle")}:</b> {_e(p.get("angle"))}</p>')
        o.append(f'<h3>🎬 {L("لمبی ویڈیو", "Long video")}</h3>{_copy(lg.get("title"))}'
                 f'<p><b>{L("تھمب نیل", "Thumbnail")}:</b> {_e(lg.get("thumb"))}</p><p><b>{L("ہک", "Hook")}:</b> {_e(lg.get("hook"))}</p>'
                 "<ol>" + "".join(f"<li>{_e(x)}</li>" for x in lg.get("outline") or []) + "</ol>")
        for j, s in enumerate(p.get("shorts") or [], 1):
            o.append(f'<details><summary>📱 {L("شارٹ", "Short")} {j}: {_e(s.get("title"))}</summary>'
                     f'<p><b>{L("ہک", "Hook")}:</b> {_e(s.get("hook"))}</p>{_copy(s.get("script"))}<p class="muted">{_e(s.get("cta"))}</p></details>')
        c = p.get("carousel") or {}
        if c:
            o.append(f'<details><summary>🖼️ {L("کیروسل", "Carousel")}: {_e(c.get("title"))}</summary><ol>'
                     + "".join(f"<li>{_e(x)}</li>" for x in c.get("slides") or []) + "</ol></details>")
        ps = p.get("posts") or {}
        o.append(f'<details><summary>📣 {L("سوشل میڈیا پوسٹیں", "Social posts")}</summary>'
                 + "".join(f"<p><b>X:</b></p>{_copy(x)}" for x in ps.get("x") or [])
                 + "".join(f"<p><b>{n}:</b></p>{_copy(ps.get(k))}" for k, n in
                           (("facebook", "Facebook"), ("instagram", "Instagram"), ("linkedin", "LinkedIn")) if ps.get(k))
                 + "</details>")
        a = p.get("article") or {}
        if a:
            o.append(f'<details><summary>📝 {L("مضمون", "Article")}: {_e(a.get("title"))}</summary><ol>'
                     + "".join(f"<li>{_e(x)}</li>" for x in a.get("outline") or []) + "</ol></details>")
        o.append("</div>")
    o.append(f'<h2>🪝 {L("ہک کے آزمودہ انداز", "Proven hook patterns")}</h2><div class="tbl"><table>'
             f'<tr><th>{L("انداز", "Pattern")}</th><th>{L("ہمارے لیے مثال", "Our version")}</th></tr>')
    for h in d.get("hook_patterns") or []:
        o.append(f'<tr><td>{_e(h.get("pattern"))}</td><td><b>{_e(h.get("example"))}</b></td></tr>')
    o.append(f'</table></div><h2>👀 {L("مقابل چینلوں کی تازہ ویڈیوز (سب سے زیادہ دیکھی گئی)", "Competitors: most viewed recent videos")}</h2><div class="tbl"><table>')
    for v in d.get("_competitors") or []:
        o.append(f'<tr><td>{_e(v["channel"])}</td><td><a href="{_e(v["url"])}">{_e(v["title"])}</a></td>'
                 f'<td class="num">{v["views"]:,}</td><td class="muted">{_e(v["date"])}</td></tr>')
    o.append(f'</table></div><p class="muted">{L("خودکار روزنامچہ", "Automatic daily desk")} · {day} · '
             f'{L("ماخذ: عوامی RSS اور یوٹیوب فیڈ؛ تجزیہ: جیمنائی", "sources: public RSS + YouTube feeds; analysis: Gemini")}</p></div>')
    return "\n".join(o)


def main(niches: list[str]) -> None:
    OUT.mkdir(exist_ok=True)
    day = dt.datetime.now(TZ).strftime("%Y-%m-%d")
    idx_p = OUT / "index.json"
    idx = json.loads(idx_p.read_text(encoding="utf-8")) if idx_p.exists() else {}
    for n in niches:
        try:
            d = build(n)
        except Exception as e:
            traceback.print_exc()
            note(f"{n}: FAILED {e}")
            continue
        (OUT / f"{n}.html").write_text(render(n, d, day), encoding="utf-8")
        (OUT / f"{n}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        (OUT / f"{n}_brief.txt").write_text(insight.brief(n, data=(d["_competitors"], d["_bank"])), encoding="utf-8")
        cfg = NICHES[n]
        idx[n] = {"date": day, "file": f"desk/{n}.html", "label": cfg["label"],
                  "title": f"روزنامچہ — {cfg['name']} — {day}"}
        print(f"desk {n}: {len(d.get('topics', []))} topics, {len(d.get('packages', []))} packages")
    idx_p.write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "log.txt").write_text("\n".join(LOG), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:] or list(NICHES))
