"""مقابل چینل، ہک بینک اور انداز نامہ — سب مفت (یوٹیوب کی سرکاری RSS، کوئی چابی نہیں)۔

ہر «شعبہ» (news / toolscape / nawa) کے مقابل چینل news/competitors.json میں ہیں۔
"@handle|regex" لکھیں تو اس چینل کی صرف وہ ویڈیوز لی جائیں گی جن کے عنوان میں regex ملے (مثلاً عام خبروں کے چینل سے صرف AI والی)۔
"""
import datetime as dt
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

from .base import ROOT

DATA = ROOT / "state"
IDS = DATA / "competitor_ids.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
      "Accept-Language": "en-US,en;q=0.9"}
NS = {"a": "http://www.w3.org/2005/Atom", "m": "http://search.yahoo.com/mrss/",
      "yt": "http://www.youtube.com/xml/schemas/2015"}


def log(msg: str) -> None:
    print(f"[insight] {msg}", flush=True)


def _read(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def competitors(niche: str) -> list:
    return _read(ROOT / "news" / "competitors.json", {}).get(niche, [])


def _bank_path(niche: str) -> Path:
    return DATA / ("hook_bank.json" if niche == "news" else f"hook_bank_{niche}.json")


def _channel_id(handle: str, cache: dict) -> str:
    if handle.startswith("UC"):
        return handle
    if handle in cache:
        return cache[handle]
    r = requests.get(f"https://www.youtube.com/{handle if handle.startswith('@') else '@' + handle}",
                     headers=UA, cookies={"CONSENT": "YES+1"}, timeout=25)
    m = (re.search(r'"externalId":"(UC[\w-]{22})"', r.text) or re.search(r'"channelId":"(UC[\w-]{22})"', r.text)
         or re.search(r'channel_id=(UC[\w-]{22})', r.text))
    if not m:
        raise RuntimeError("channel id not found")
    cache[handle] = m.group(1)
    return cache[handle]


def competitor_videos(niche: str = "news", max_age_days: int = 30) -> list:
    """[{channel, title, views, date, url}] مقابل چینلوں کی تازہ ویڈیوز"""
    cache = _read(IDS, {})
    out, cutoff = [], dt.datetime.utcnow() - dt.timedelta(days=max_age_days)
    for entry in competitors(niche):
        h, _, pat = entry.partition("|")
        try:
            cid = _channel_id(h, cache)
            r = requests.get(f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}", headers=UA, timeout=25)
            r.raise_for_status()
            root = ET.fromstring(r.text)
            name = root.findtext("a:title", "", NS)
            n = 0
            for e in root.findall("a:entry", NS):
                date = dt.datetime.fromisoformat(e.findtext("a:published", "", NS)[:19])
                title = e.findtext("a:title", "", NS)
                if date < cutoff or (pat and not re.search(pat, title, re.I)):
                    continue
                st = e.find("m:group/m:community/m:statistics", NS)
                out.append({"channel": name, "title": title,
                            "views": int(st.get("views", 0)) if st is not None else 0,
                            "date": f"{date:%Y-%m-%d}",
                            "url": f"https://youtu.be/{e.findtext('yt:videoId', '', NS)}"})
                n += 1
            log(f"{niche}: {n} videos from {name}")
        except Exception as e:  # ایک خراب چینل سے کام نہ رکے
            log(f"{niche}: skipped {h} ({e})")
    DATA.mkdir(exist_ok=True)
    IDS.write_text(json.dumps(cache, indent=1), encoding="utf-8")
    return out


def update_bank(niche: str, videos: list, keep: int = 300) -> list:
    p = _bank_path(niche)
    bank = {v["url"]: v for v in _read(p, [])}
    for v in videos:
        bank[v["url"]] = v
    items = sorted(bank.values(), key=lambda v: -v.get("views", 0))[:keep]
    DATA.mkdir(exist_ok=True)
    p.write_text(json.dumps(items, indent=1, ensure_ascii=False), encoding="utf-8")
    return items


def style_guide(niche: str = "news") -> str:
    p = ROOT / "news" / ("style.md" if niche == "news" else f"style_{niche}.md")
    return p.read_text(encoding="utf-8").strip() if p.exists() else ""


def gather(niche: str = "news") -> tuple[list, list]:
    recent = competitor_videos(niche)
    return sorted(recent, key=lambda v: -v["views"]), update_bank(niche, recent)


def brief(niche: str = "news", n_recent: int = 40, n_bank: int = 25, data: tuple | None = None) -> str:
    recent, bank = data or gather(niche)
    if not recent and not bank:
        return "(competitor data unavailable today — rely on the style guide)"
    fmt = lambda v: f"- [{v['channel']}] \"{v['title']}\" — {v['views']:,} views ({v['date']})"
    return ("COMPETITORS' LATEST VIDEOS (last 30 days, most viewed first):\n" + "\n".join(map(fmt, recent[:n_recent]))
            + "\n\nHOOK BANK (best performing titles collected so far — learn the PATTERN, never copy):\n"
            + "\n".join(map(fmt, bank[:n_bank])))


VIRAL_RULES = """مقابل چینل اور ہک کے اصول:
- اوپر مقابل چینلوں کی تازہ ویڈیوز اور ان کے ویوز دیکھیں۔ جو خبر وہ پہلے دے چکے ہوں، اس میں وہ پہلو لائیں جو انہوں نے چھوڑا (عام آدمی پر اثر، پاکستان/ہندوستان کے لیے اہمیت، آگے کیا ہوگا)۔
- «youtube_title»، «thumb_text» اور آغاز کا پہلا جملہ مقابلین کے عنوانوں سے زیادہ مضبوط ہو: سب سے زیادہ دیکھے گئے عنوانوں کا انداز سیکھیں (واضح خبر، بڑا نام، تجسس)، مگر ان کے الفاظ نقل نہیں؛ کوئی جھوٹا یا سنسنی خیز دعویٰ نہیں جو بلیٹن میں نہ ہو۔
- «viral» ایمان داری سے بھریں: 0 تا 100 = اس بلیٹن کے مقابلین کی اوسط سے بہتر چلنے کا حقیقی امکان۔"""


if __name__ == "__main__":
    (ROOT / "state" / "insight_test.txt").write_text(brief(), encoding="utf-8")
