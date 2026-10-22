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

from .base import ROOT, generate_json
from . import insight

OUT = ROOT / "desk"
TZ = dt.timezone(dt.timedelta(hours=3))
UA = {"User-Agent": "Mozilla/5.0 (FarooqiDailyDesk RSS reader)"}

NICHES = {
    "news": {
        "name": "فاروقی اے آئی نیوز", "label": "AI News", "rtl": True, "lang": "اردو",
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
        "name": "Toolscape", "label": "Toolscape", "rtl": False, "lang": "English",
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
        "name": "نوائے فاروقی", "label": "Nawa-e-Farooqi", "rtl": True, "lang": "اردو",
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
use only what the trending items and competitor titles show. Viral scores are realistic estimates, not hype.
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


def build(niche: str) -> dict:
    cfg = NICHES[niche]
    data = insight.gather(niche)
    heads = [h for u in cfg["feeds"] for h in _items(u)]
    user = (f"Today: {dt.datetime.now(TZ):%A %d %B %Y}\n\nTRENDING ITEMS (last 1-3 days):\n" + "\n".join(heads[:120])
            + "\n\n" + insight.brief(niche, data=data) + "\n\nCHANNEL STYLE GUIDE:\n" + insight.style_guide(niche))
    d = generate_json(SYSTEM.format(lang=cfg["lang"], script=" (Urdu script, never Roman Urdu)" if cfg["rtl"] else "",
                                    extra=EXTRA.get(niche, ""), name=cfg["name"], about=cfg["about"]), user)
    d["_competitors"] = data[0][:15]
    d["_bank"] = data[1][:15]
    return d


# ---------------- HTML ----------------

CSS = """<style>
.dd{font-family:'Noto Nastaliq Urdu','Jameel Noori Nastaleeq',system-ui,sans-serif;color:#1d2433;line-height:1.9;max-width:900px;margin:auto}
.dd.ltr{font-family:system-ui,-apple-system,'Segoe UI',sans-serif;line-height:1.6}
.dd h2{font-size:21px;margin:28px 0 10px;padding:6px 12px;background:#12324a;color:#fff;border-radius:8px}
.dd h3{font-size:18px;margin:18px 0 6px;color:#12324a}
.dd .sum{background:#eef4fa;border-radius:10px;padding:10px 14px}
.dd table{width:100%;border-collapse:collapse;font-size:15px}
.dd td,.dd th{border-bottom:1px solid #e3e7ee;padding:6px 8px;vertical-align:top;text-align:start}
.dd th{background:#f5f7fa}
.dd .bar{display:inline-block;height:9px;border-radius:5px;background:#e8a33d}
.dd .card{border:1px solid #dfe5ee;border-radius:12px;padding:12px 16px;margin:14px 0;background:#fff}
.dd .score{float:inline-end;font-weight:700;background:#fff3e0;color:#b45309;border-radius:20px;padding:2px 12px}
.dd .copy{white-space:pre-wrap;background:#f7f8fa;border:1px dashed #cdd5e0;border-radius:8px;padding:8px 12px;margin:6px 0;font-size:15px}
.dd .muted{color:#667085;font-size:14px}
.dd details{margin:6px 0}.dd summary{cursor:pointer;font-weight:700;color:#12324a}
.dd a{color:#1d4ed8}
</style>"""


def _e(x) -> str:
    return H.escape(str(x or ""))


def _copy(x) -> str:
    return f'<div class="copy">{_e(x)}</div>' if x else ""


def render(niche: str, d: dict, day: str) -> str:
    cfg = NICHES[niche]
    rtl = cfg["rtl"]
    L = (lambda ur, en: ur if rtl else en)
    o = [CSS, f'<div class="dd{"" if rtl else " ltr"}" dir="{"rtl" if rtl else "ltr"}">',
         f'<p class="sum">{_e(d.get("summary"))}</p>', f'<h2>🔥 {L("آج کے 10 ٹرینڈنگ موضوعات", "Top 10 trending topics today")}</h2>',
         f'<table><tr><th>#</th><th>{L("موضوع", "Topic")}</th><th>{L("ٹرینڈ", "Trend")}</th><th>{L("کیوں / کہاں", "Why / where")}</th></tr>']
    for i, t in enumerate(d.get("topics", [])[:10], 1):
        tr = max(1, min(10, int(t.get("trend") or 5))) if str(t.get("trend", "")).isdigit() else 5
        o.append(f'<tr><td>{i}</td><td><b>{_e(t.get("title"))}</b></td><td><span class="bar" style="width:{tr * 8}px"></span> {tr}/10</td>'
                 f'<td>{_e(t.get("why"))}<br><span class="muted">{_e(", ".join(t.get("sources") or []))}</span></td></tr>')
    o.append("</table>")
    for i, p in enumerate(d.get("packages", [])[:3], 1):
        v, lg = p.get("viral") or {}, p.get("long") or {}
        o.append(f'<h2>📦 {L("پیکج", "Package")} {i}: {_e(p.get("topic"))}</h2><div class="card">'
                 f'<span class="score">{L("وائرل امکان", "Viral chance")} {_e(v.get("score", "?"))}/100</span>'
                 f'<p>{_e(v.get("why"))}</p><p><b>{L("مقابلین", "Competitors")}:</b> {_e(p.get("competitors"))}</p>'
                 f'<p><b>{L("ہمارا زاویہ", "Our angle")}:</b> {_e(p.get("angle"))}</p></div>')
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
    o.append(f'<h2>🪝 {L("ہک کے آزمودہ انداز", "Proven hook patterns")}</h2><table>')
    for h in d.get("hook_patterns") or []:
        o.append(f'<tr><td>{_e(h.get("pattern"))}</td><td><b>{_e(h.get("example"))}</b></td></tr>')
    o.append(f'</table><h2>👀 {L("مقابل چینلوں کی تازہ ویڈیوز (سب سے زیادہ دیکھی گئی)", "Competitors: most viewed recent videos")}</h2><table>')
    for v in d.get("_competitors") or []:
        o.append(f'<tr><td>{_e(v["channel"])}</td><td><a href="{_e(v["url"])}">{_e(v["title"])}</a></td>'
                 f'<td>{v["views"]:,}</td><td class="muted">{_e(v["date"])}</td></tr>')
    o.append(f'</table><p class="muted">{L("خودکار روزنامچہ", "Automatic daily desk")} · {day} · '
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
        except Exception:
            traceback.print_exc()
            continue
        (OUT / f"{n}.html").write_text(render(n, d, day), encoding="utf-8")
        (OUT / f"{n}_brief.txt").write_text(insight.brief(n, data=(d["_competitors"], d["_bank"])), encoding="utf-8")
        cfg = NICHES[n]
        idx[n] = {"date": day, "file": f"desk/{n}.html", "label": cfg["label"],
                  "title": f"روزنامچہ — {cfg['name']} — {day}"}
        print(f"desk {n}: {len(d.get('topics', []))} topics, {len(d.get('packages', []))} packages")
    idx_p.write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:] or list(NICHES))
